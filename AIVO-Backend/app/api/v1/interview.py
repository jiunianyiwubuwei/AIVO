"""面试 API"""

import json
import base64
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from pydantic import BaseModel

from app.core.schemas.interview import (
    CreateInterviewRequest,
    InterviewSessionResponse,
    MessageRequest,
    MessageResponse,
    InterviewResult,
)
from app.core.schemas.response import BaseResponse, PageResponse
from app.core.security import get_current_user
from app.infrastructure.database.connection import get_db
from app.infrastructure.database.models import User
from app.application.interview.interview_service import InterviewService

router = APIRouter()


def get_interview_service(db: AsyncSession = Depends(get_db)) -> InterviewService:
    return InterviewService(db)


@router.get("/conversations")
async def list_interview_conversations(
    current: int = Query(default=1, ge=1, description="当前页"),
    size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试会话列表（别名路由，兼容前端）"""
    skip = (current - 1) * size
    items, total = await service.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=size,
    )

    # 转换数据格式，添加业务相关信息
    data = []
    for item in items:
        # 优先从 MongoDB 快照获取面试分数（对于历史数据）
        interview_score = item.interview_score or 0
        if interview_score == 0:
            snapshot = await service.get_snapshot(item.session_id)
            if snapshot:
                # 优先使用 interview_score（百分比形式）
                interview_score = snapshot.get("interview_score", 0)
                if interview_score == 0:
                    # 其次使用 total_score 转换为百分比
                    total_score = snapshot.get("total_score", 0)
                    questions = snapshot.get("questions", [])
                    total_possible = len(questions) * 20 if questions else 5 * 20
                    interview_score = int((total_score / total_possible) * 100) if total_possible > 0 else 0
                    if interview_score == 0:
                        # 最后从 answers 中计算
                        answers = snapshot.get("answers", [])
                        raw_score = sum(a.get("score", 0) for a in answers if a.get("score"))
                        if raw_score > 0:
                            interview_score = int((raw_score / total_possible) * 100) if total_possible > 0 else 0
        
        # 获取简历分数
        resume_score = item.resume_score or 0

        # 根据权重计算综合评分
        snapshot_data = await service.get_snapshot(item.session_id)
        demeanor_report = snapshot_data.get("demeanor_report") if snapshot_data else None

        if demeanor_report:
            llm_content = demeanor_report.get("llm_content_score", 0) or 0
            llm_posture = demeanor_report.get("llm_posture_score", 0) or 0
            llm_speech = demeanor_report.get("llm_speech_score", 0) or 0
            content_100 = (llm_content / 40) * 100 if llm_content > 0 else 0
            posture_100 = (llm_posture / 30) * 100 if llm_posture > 0 else 0
            speech_100 = (llm_speech / 30) * 100 if llm_speech > 0 else 0
            composite_score = int(round(
                content_100 * 0.30 +
                posture_100 * 0.20 +
                speech_100 * 0.20 +
                resume_score * 0.15 +
                interview_score * 0.15
            ))
        else:
            composite_score = int((resume_score * 0.4 + interview_score * 0.6)) if resume_score > 0 and interview_score > 0 else (interview_score or resume_score)

        # 格式化时长
        duration_str = ""
        if item.duration_seconds:
            minutes = item.duration_seconds // 60
            seconds = item.duration_seconds % 60
            duration_str = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

        # 状态中文映射
        status_map = {
            "INIT": "待开始",
            "IN_PROGRESS": "面试中",
            "ASKING": "提问中",
            "EVALUATING": "评估中",
            "FOLLOW_UP": "追问中",
            "COMPLETED": "已完成",
            "FINISHED": "已完成",
        }
        status_text = status_map.get(item.interview_status, item.interview_status or "未知")

        data.append({
            "id": item.id,
            "sessionId": item.session_id,
            "interviewDirection": item.interview_direction or "通用面试",
            "interviewStatus": item.interview_status,
            "statusText": status_text,
            "resumeScore": resume_score,
            "interviewScore": interview_score,
            "compositeScore": composite_score,
            "questionCount": item.question_count or 0,
            "durationSeconds": item.duration_seconds,
            "durationText": duration_str,
            "startTime": item.start_time.isoformat() if item.start_time else None,
            "endTime": item.end_time.isoformat() if item.end_time else None,
            "createTime": item.create_time.isoformat() if item.create_time else None,
        })

    return {
        "code": 200,
        "message": "success",
        "success": True,
        "data": data,
        "page_info": {
            "page": current,
            "page_size": size,
            "total": total,
        }
    }


@router.post("/sessions", response_model=BaseResponse)
async def create_interview_session(
    request: CreateInterviewRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """创建面试会话"""
    interview = await service.create_session(
        user_id=current_user.id,
        interview_direction=request.interview_direction,
        resume_content=request.resume_content,
    )
    return BaseResponse(
        success=True,
        message="面试会话创建成功",
        data={
            "sessionId": interview.session_id,
            "status": interview.interview_status,
        }
    )


@router.get("/sessions", response_model=PageResponse[InterviewSessionResponse])
async def list_interview_sessions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试会话列表"""
    items, total = await service.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    # 状态中文映射
    status_map = {
        "INIT": "待开始",
        "IN_PROGRESS": "面试中",
        "ASKING": "提问中",
        "EVALUATING": "评估中",
        "FOLLOW_UP": "追问中",
        "COMPLETED": "已完成",
        "FINISHED": "已完成",
    }

    # Convert to dict with enhanced business info
    data = []
    for item in items:
        # 获取分数
        resume_score = item.resume_score or 0
        interview_score = item.interview_score or 0

        # 根据权重计算综合评分
        snapshot = await service.get_by_session_id(item.session_id)
        snapshot_data = await service.get_snapshot(item.session_id) if snapshot else None
        demeanor_report = snapshot_data.get("demeanor_report") if snapshot_data else None

        if demeanor_report:
            llm_content = demeanor_report.get("llm_content_score", 0) or 0
            llm_posture = demeanor_report.get("llm_posture_score", 0) or 0
            llm_speech = demeanor_report.get("llm_speech_score", 0) or 0
            content_100 = (llm_content / 40) * 100 if llm_content > 0 else 0
            posture_100 = (llm_posture / 30) * 100 if llm_posture > 0 else 0
            speech_100 = (llm_speech / 30) * 100 if llm_speech > 0 else 0
            composite_score = int(round(
                content_100 * 0.30 +
                posture_100 * 0.20 +
                speech_100 * 0.20 +
                resume_score * 0.15 +
                interview_score * 0.15
            ))
        else:
            composite_score = int((resume_score * 0.4 + interview_score * 0.6)) if resume_score > 0 and interview_score > 0 else (interview_score or resume_score)

        # 格式化时长
        duration_str = ""
        if item.duration_seconds:
            minutes = item.duration_seconds // 60
            seconds = item.duration_seconds % 60
            duration_str = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

        data.append({
            "id": item.id,
            "user_id": item.user_id,
            "session_id": item.session_id,
            "interview_direction": item.interview_direction or "通用面试",
            "interview_status": item.interview_status,
            "status_text": status_map.get(item.interview_status, item.interview_status or "未知"),
            "resume_score": resume_score,
            "interview_score": interview_score,
            "composite_score": composite_score,
            "question_count": item.question_count or 0,
            "duration_seconds": item.duration_seconds,
            "duration_text": duration_str,
            "start_time": item.start_time.isoformat() if item.start_time else None,
            "end_time": item.end_time.isoformat() if item.end_time else None,
            "interview_suggestions": item.interview_suggestions,
            "create_time": item.create_time.isoformat() if item.create_time else None,
        })
    return PageResponse(
        data=data,
        page_info={
            "page": skip // limit + 1,
            "page_size": limit,
            "total": total,
        }
    )


@router.get("/sessions/{session_id}", response_model=BaseResponse[InterviewSessionResponse])
async def get_interview_session(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试会话详情"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )
    return BaseResponse(data=InterviewSessionResponse.model_validate(interview))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取会话消息历史"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    messages = await service.get_messages(session_id, limit)
    return BaseResponse(data=messages)


@router.get("/sessions/{session_id}/snapshot")
async def get_interview_snapshot(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试快照"""
    snapshot = await service.get_snapshot(session_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="快照不存在",
        )
    return BaseResponse(data=snapshot)


@router.get("/sessions/{session_id}/resume/preview")
async def get_resume_preview(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取简历预览（返回文件流）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )
    # 从快照中获取简历内容
    snapshot = await service.get_snapshot(session_id)
    resume_content = None
    if snapshot:
        resume_content = snapshot.get("resume_content")

    if not resume_content:
        # 返回空 PDF 占位内容（使用标准字体，不依赖嵌入字体）
        # PDF 1.4 规范，使用 Helvetica 内置字体（所有 PDF 阅读器都支持）
        placeholder_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F0 4 0 R >> >> "
            b"/Contents 5 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            b"5 0 obj\n<< /Length 78 >>\n"
            b"stream\n"
            b"BT\n"
            b"/F0 18 Tf\n"
            b"180 520 Td\n"
            b"(No Resume Uploaded) Tj\n"
            b"0 -30 Td\n"
            b"/F0 12 Tf\n"
            b"(Please upload your resume to start the interview.) Tj\n"
            b"ET\n"
            b"endstream\nendobj\n"
            b"xref\n0 6\n"
            b"0000000000 65535 f\n"
            b"0000000009 00000 n\n"
            b"0000000058 00000 n\n"
            b"0000000115 00000 n\n"
            b"0000000200 00000 n\n"
            b"0000000316 00000 n\n"
            b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
            b"startxref\n449\n"
            b"%%EOF"
        )
        return Response(
            content=placeholder_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=resume_{session_id}.pdf",
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            }
        )

    # 如果简历内容是 base64，解码后返回
    import base64
    try:
        file_content = base64.b64decode(resume_content)
    except Exception:
        # 如果不是 base64，直接作为文本
        file_content = resume_content.encode("utf-8")

    return Response(
        content=file_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=resume_{session_id}.pdf",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        }
    )


@router.get("/sessions/{session_id}/current-question")
async def get_current_question(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取当前问题"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )
    # 获取当前问题（从 MongoDB 中获取）
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "isSuccess": True,
                "finished": True,
                "questionContent": None,
                "questionNumber": None,
                "nextQuestion": None,
                "nextQuestionNumber": None,
                "isFollowUp": False,
                "followUpCount": 0,
            },
        }

    current_question = snapshot.get("current_question")
    answered_count = snapshot.get("answered_count", 0)
    total_questions = snapshot.get("total_questions", 5)
    is_finished = answered_count >= total_questions
    current_follow_up_count = snapshot.get("current_follow_up_count", 0)

    # 构建符合前端期望的格式
    response_data = {
        "isSuccess": True,
        "finished": is_finished,
        "questionContent": current_question.get("content") if current_question else None,
        "questionNumber": current_question.get("number") if current_question else None,
        "nextQuestion": current_question.get("content") if current_question and not is_finished else None,
        "nextQuestionNumber": current_question.get("number") if current_question and not is_finished else None,
        "isFollowUp": current_follow_up_count > 0,
        "followUpCount": current_follow_up_count,
    }
    return {
        "code": 200,
        "message": "success",
        "data": response_data,
    }


@router.get("/sessions/{session_id}/next-question")
async def get_next_question(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取下一个问题"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )
    # 获取下一个问题
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    return {
        "code": 200,
        "message": "success",
        "data": snapshot.get("next_question"),
    }


def _serialize_snapshot(data):
    """将 MongoDB 数据中的 ObjectId 转换为字符串"""
    if isinstance(data, ObjectId):
        return str(data)
    if isinstance(data, dict):
        return {k: _serialize_snapshot(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_snapshot(item) for item in data]
    return data


@router.get("/sessions/{session_id}/restore")
async def restore_interview_session(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """恢复面试会话状态"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )
    # 获取快照数据
    snapshot = await service.get_snapshot(session_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="暂无会话快照",
        )
    # 序列化 ObjectId
    serialized_snapshot = _serialize_snapshot(snapshot)

    # 构建符合前端期望的恢复响应格式
    resume_filename = snapshot.get("resume_filename", "resume.pdf")
    resume_file_url = f"/xunzhi/v1/interview/sessions/{session_id}/resume/preview"

    # 获取简历分数和建议
    resume_score = interview.resume_score
    interview_suggestions = snapshot.get("interview_suggestions", {})

    return {
        "code": 200,
        "message": "success",
        "data": {
            **serialized_snapshot,
            "sessionId": session_id,
            "status": interview.interview_status,
            "resumeFileUrl": resume_file_url,
            "resumeFilename": resume_filename,
            "resumeScore": resume_score or 0,
            "suggestions": interview_suggestions or {},
            "interviewType": interview.interview_direction,
            "interviewDirection": interview.interview_direction,
        }
    }


@router.post("/sessions/{session_id}/interview-questions")
async def generate_interview_questions(
    session_id: str,
    resume_pdf: Optional[UploadFile] = File(None, description="简历PDF文件(可选)"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """生成面试问题（上传简历后调用）"""
    import base64
    from fastapi import Request
    
    # 记录请求信息
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    # 读取简历文件内容（如果提供了）
    resume_content = None
    resume_base64 = None
    if resume_pdf:
        content = await resume_pdf.read()
        if content:
            resume_base64 = base64.b64encode(content).decode("utf-8")
            try:
                if resume_pdf.content_type == "application/pdf":
                    try:
                        import fitz
                        pdf_document = fitz.open(stream=content, filetype="pdf")
                        text_parts = []
                        for page_num, page in enumerate(pdf_document):
                            text = page.get_text()
                            print(f"[interview-questions] Page {page_num + 1} text length: {len(text)}")
                            if not text.strip():
                                # Try OCR if text extraction fails
                                try:
                                    import pytesseract
                                    from PIL import Image
                                    pix = page.get_pixmap(dpi=300)
                                    img_data = pix.tobytes("png")
                                    import io
                                    img = Image.open(io.BytesIO(img_data))
                                    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                                    print(f"[interview-questions] OCR text length: {len(text)}")
                                except ImportError:
                                    print("[interview-questions] pytesseract not installed, skipping OCR")
                                except Exception as e:
                                    print(f"[interview-questions] OCR failed: {e}")
                            if text.strip():
                                text_parts.append(f"Page {page_num + 1}:\n{text.strip()}")
                        resume_content = "\n\n".join(text_parts) if text_parts else None
                        pdf_document.close()
                        print(f"[interview-questions] Total extracted text: {len(resume_content) if resume_content else 0} chars")
                    except ImportError as e:
                        print(f"[interview-questions] fitz not installed: {e}")
                        resume_content = None
                    except Exception as e:
                        print(f"[interview-questions] PDF extraction failed: {e}")
                        resume_content = None
                else:
                    resume_content = content.decode("utf-8", errors="ignore")
            except Exception:
                resume_content = None
        else:
            resume_content = None
    else:
        pass  # No resume file provided

    # 调试：检查简历内容
    if resume_content:
        print(f"[interview-questions] Resume extracted: {len(resume_content)} chars, preview: {resume_content[:200]}...")

    # 调用 workflow 生成问题
    from app.workflow.interview_graph import run_interview_init
    result = await run_interview_init(
        session_id=session_id,
        user_id=current_user.id,
        interview_direction=interview.interview_direction,
        resume_content=resume_content,
    )

    questions = result.get("questions", [])
    resume_score = result.get("resume_score")
    resume_analysis = result.get("resume_analysis")

    # 更新面试状态，并保存简历评分
    await service.update_status(
        session_id,
        "ASKING",
        question_count=len(questions),
        resume_score=resume_score,
    )

    # 保存快照数据到 MongoDB（包含简历内容用于预览）
    # 初始化流程状态（与 Java 版本一致）
    flow_state = {
        "status": "ASKING",
        "current_index": 0,
        "current_question_number": questions[0].get("number") if questions else "1",
        "total_questions": len(questions),
        "follow_up_count": 0,
        "max_follow_up": 2,
        "version": 1,
    }

    snapshot_data = {
        "questions": questions,
        "current_question": questions[0] if questions else None,
        "current_question_index": 0,
        "answered_count": 0,
        "total_questions": len(questions),
        "flow_state": flow_state,
    }
    if resume_base64:
        snapshot_data["resume_content"] = resume_base64
        snapshot_data["resume_filename"] = resume_pdf.filename
    if resume_analysis:
        snapshot_data["resume_analysis"] = resume_analysis

    await service.save_snapshot(session_id=session_id, data=snapshot_data)

    # 构建符合前端期望的响应格式
    # 返回完整的预览 URL（后端会从快照中读取简历内容）
    preview_url = f"/xunzhi/v1/interview/sessions/{session_id}/resume/preview"

    questions_dict = {}
    suggestions_dict = {}
    for i, q in enumerate(questions):
        # 使用纯数字作为题号，与 Java 版本一致
        q_id = str(i + 1)
        q["number"] = q_id
        questions_dict[q_id] = q.get("content", "")

    return BaseResponse(data={
        "id": str(interview.id),
        "sessionId": session_id,
        "userName": current_user.username,
        "questions": questions_dict,
        "suggestions": suggestions_dict,
        "interviewType": interview.interview_direction,
        "interviewDirection": interview.interview_direction,
        "resumeFileUrl": preview_url,
        "resumeFilename": resume_pdf.filename if resume_pdf else None,
        "responseTime": 0,
        "tokenCount": 0,
        "isSuccess": 1,
        "resumeScore": resume_score if resume_score is not None else 0,
        "resumeAnalysis": resume_analysis if resume_analysis else {},
    })


@router.post("/sessions/{session_id}/resume")
async def upload_resume(
    session_id: str,
    resume_file: UploadFile = File(..., description="简历文件"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """上传简历文件并触发出题"""
    import base64

    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    # 读取文件内容
    content = await resume_file.read()
    file_content = base64.b64encode(content).decode("utf-8")

    # 尝试提取简历文本（用于生成问题）
    resume_text = None
    try:
        # 如果是 PDF，尝试使用 PyMuPDF 解析
        if resume_file.content_type == "application/pdf":
            try:
                import fitz  # PyMuPDF
                import io
                pdf_document = fitz.open(stream=content, filetype="pdf")
                text_parts = []
                for page in pdf_document:
                    text_parts.append(page.get_text())
                resume_text = "\n".join(text_parts)
                pdf_document.close()
            except ImportError:
                # 如果 PyMuPDF 未安装，回退到简单解码
                try:
                    decoded_content = base64.b64decode(content)
                    resume_text = decoded_content.decode("utf-8", errors="ignore")
                except Exception:
                    resume_text = None
        else:
            # 如果不是 PDF，直接解码
            try:
                resume_text = content.decode("utf-8", errors="ignore")
            except Exception:
                resume_text = None
    except Exception:
        resume_text = None

    # 调用 workflow 生成问题
    from app.workflow.interview_graph import run_interview_init
    questions = []
    try:
        questions = await run_interview_init(
            session_id=session_id,
            user_id=current_user.id,
            interview_direction=interview.interview_direction,
            resume_content=resume_text,
        )
    except Exception as e:
        # 出题失败不影响简历上传
        print(f"生成问题失败: {e}")

    # 保存快照数据到 MongoDB
    snapshot_data = {
        "resume_content": file_content,
        "resume_filename": resume_file.filename,
        "resume_content_type": resume_file.content_type,
        "resume_text": resume_text,
    }
    if questions:
        # 初始化流程状态（与 Java 版本一致）
        flow_state = {
            "status": "ASKING",
            "current_index": 0,
            "current_question_number": questions[0].get("number") if questions else "1",
            "total_questions": len(questions),
            "follow_up_count": 0,
            "max_follow_up": 2,
            "version": 1,
        }
        snapshot_data.update({
            "questions": questions,
            "current_question": questions[0] if questions else None,
            "current_question_index": 0,
            "answered_count": 0,
            "total_questions": len(questions),
            "flow_state": flow_state,
        })

    await service.save_snapshot(session_id=session_id, data=snapshot_data)

    # 更新面试状态
    if questions:
        await service.update_status(session_id, "ASKING", question_count=len(questions))

    # 构建符合前端期望的响应格式
    questions_dict = {}
    suggestions_dict = {}
    for i, q in enumerate(questions):
        # 使用纯数字作为题号，与 Java 版本一致
        q_id = str(i + 1)
        q["number"] = q_id
        questions_dict[q_id] = q.get("content", "")

    return {
        "code": 200,
        "message": "success",
        "data": {
            "fileName": resume_file.filename,
            "fileUrl": None,
            "hasFile": True,
            "questions": questions_dict,
            "suggestions": suggestions_dict,
            "interviewType": interview.interview_direction,
            "resumeFileUrl": f"resume_{session_id}.pdf",
            "responseTime": 0,
            "tokenCount": 0,
            "isSuccess": 1,
            "resumeScore": 80,
        }
    }


@router.post("/sessions/{session_id}/voice/transcribe")
async def transcribe_audio(
    session_id: str,
    audio_file: UploadFile = File(..., description="音频文件"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """语音识别 - 将音频转为文字（使用 Whisper）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    # 读取音频文件
    audio_content = await audio_file.read()

    # 调用 Whisper 进行语音识别
    from app.integrations.whisper import whisper_service
    try:
        result = await whisper_service.transcribe_audio_data(
            audio_data=audio_content,
            sample_rate=16000,
            language="zh",
        )
        return {
            "code": 200,
            "message": "success",
            "data": {
                "text": result["text"],
                "language": result["language"],
                "segments": result.get("segments", []),
            }
        }
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"语音识别失败: {str(e)}",
        )


class DemeanorFrameRequest(BaseModel):
    """仪态分析帧请求"""
    timestamp: int = 0


@router.post("/sessions/{session_id}/demeanor/analyze-frame")
async def analyze_demeanor_frame(
    session_id: str,
    frame_image: UploadFile = File(..., description="视频帧图片"),
    timestamp_ms: int = Query(default=0, description="时间戳（毫秒）"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """仪态分析 - 分析单帧图像（使用 MediaPipe）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    import numpy as np
    import cv2

    # 读取图片数据
    image_bytes = await frame_image.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法解析图片数据",
        )

    # 调用 MediaPipe 进行分析
    from app.integrations.mediapipe import mediapipe_analyzer
    try:
        result = await mediapipe_analyzer.analyze_frame(frame, timestamp_ms=timestamp_ms)

        # 序列化结果
        response_data = {
            "face_detected": result.face_detected,
            "face_count": result.face_count,
            "face_blur_score": result.face_blur_score,
            "face_size_ratio": result.face_size_ratio,
            "confidence": result.confidence,
            "timestamp_ms": result.timestamp_ms,
        }

        if result.head_pose:
            response_data["head_pose"] = {
                "yaw": result.head_pose.yaw,
                "pitch": result.head_pose.pitch,
                "roll": result.head_pose.roll,
            }

        if result.expression:
            response_data["expression"] = {
                "happiness": result.expression.happiness,
                "sadness": result.expression.sadness,
                "anger": result.expression.anger,
                "surprise": result.expression.surprise,
                "neutral": result.expression.neutral,
                "dominant": result.expression.dominant,
            }

        return {
            "code": 200,
            "message": "success",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"仪态分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"仪态分析失败: {str(e)}",
        )


@router.post("/sessions/{session_id}/demeanor/evaluate")
async def evaluate_demeanor_result(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """仪态评估 - 获取综合评估结果（大模型打分）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    # 获取会话中的仪态数据
    snapshot = await service.get_snapshot(session_id)
    demeanor_frames = []
    if snapshot:
        demeanor_frames = snapshot.get("demeanor_frames", [])

    if not demeanor_frames:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "total_score": 70.0,
                "posture_score": 70.0,
                "expression_score": 70.0,
                "eye_contact_score": 70.0,
                "confidence_score": 70.0,
                "feedback": "暂无仪态数据",
                "suggestions": ["请确保摄像头正常工作"],
            }
        }

    # 调用仪态评估服务
    from app.application.interview.demeanor_service import demeanor_service
    from app.integrations.mediapipe import DemeanorData

    # 转换数据
    demeanor_data_list = []
    for frame in demeanor_frames:
        data = DemeanorData(
            face_detected=frame.get("face_detected", False),
            face_count=frame.get("face_count", 0),
            confidence=frame.get("confidence", 0.5),
            face_blur_score=frame.get("face_blur_score", 100.0),
            face_size_ratio=frame.get("face_size_ratio", 0.0),
            timestamp_ms=frame.get("timestamp_ms", 0),
        )
        if "head_pose" in frame:
            from app.integrations.mediapipe import HeadPose
            data.head_pose = HeadPose(**frame["head_pose"])
        if "expression" in frame:
            from app.integrations.mediapipe import ExpressionScore
            data.expression = ExpressionScore(**frame["expression"])
        demeanor_data_list.append(data)

    try:
        result = await demeanor_service.evaluate(demeanor_data_list)

        # 保存评估结果到快照
        await service.update_snapshot(session_id, {
            "demeanor_score": result.total_score,
            "demeanor_evaluation": {
                "total_score": result.total_score,
                "posture_score": result.posture_score,
                "expression_score": result.expression_score,
                "eye_contact_score": result.eye_contact_score,
                "confidence_score": result.confidence_score,
                "feedback": result.feedback,
                "suggestions": result.suggestions,
            }
        })

        return {
            "code": 200,
            "message": "success",
            "data": {
                "total_score": result.total_score,
                "posture_score": result.posture_score,
                "expression_score": result.expression_score,
                "eye_contact_score": result.eye_contact_score,
                "confidence_score": result.confidence_score,
                "feedback": result.feedback,
                "suggestions": result.suggestions,
            }
        }
    except Exception as e:
        logger.error(f"仪态评估失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"仪态评估失败: {str(e)}",
        )


@router.put("/sessions/{session_id}/finish")
async def finish_interview(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """结束面试会话"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    # 获取快照数据
    snapshot = await service.get_snapshot(session_id)

    # 计算最终统计数据
    answers = snapshot.get("answers", []) if snapshot else []
    questions = snapshot.get("questions", []) if snapshot else []

    total_score = sum(a.get("score", 0) for a in answers if a.get("score"))
    answered_count = len([a for a in answers if a.get("score") is not None])
    interview_score = total_score if answered_count > 0 else 0

    # 获取简历分数
    resume_score = interview.resume_score or 0

    # 使用大模型生成面试总结和建议
    from app.agents.ai_client import ai_client
    ai_summary = ""
    try:
        ai_summary = await ai_client.generate_summary(questions, answers)
    except Exception as e:
        print(f"[finish_interview] AI summary generation failed: {e}")
        ai_summary = ""

    # 解析 AI 返回的总结
    overall_comment = ""
    highlights = []
    improvement_tips = []
    suggestions_text = []
    suggestions = {}

    if ai_summary:
        lines = ai_summary.split("\n")
        current_section = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 检测章节标题
            lower_line = stripped.lower()
            if "整体评价" in stripped and "：" in stripped:
                current_section = "overall"
                overall_comment = stripped.split("：", 1)[-1].strip()
            elif "亮点" in stripped or "优点" in stripped:
                current_section = "highlights"
            elif "改进" in stripped or "待改进" in stripped or "不足" in stripped:
                current_section = "improvements"
            elif "建议" in stripped:
                current_section = "suggestions"
            elif current_section == "highlights" and stripped and stripped[0] in ["-", "•", "*", "·", "1", "2", "3"]:
                # 提取亮点
                text = stripped.lstrip("-•*·1234567890.、 ")
                if text:
                    highlights.append(text)
            elif current_section == "improvements" and stripped and stripped[0] in ["-", "•", "*", "·", "1", "2", "3"]:
                # 提取改进点
                text = stripped.lstrip("-•*·1234567890.、 ")
                if text:
                    improvement_tips.append(text)
            elif current_section == "suggestions" and stripped and stripped[0] in ["-", "•", "*", "·", "1", "2", "3"]:
                # 提取建议
                text = stripped.lstrip("-•*·1234567890.、 ")
                if text:
                    suggestions_text.append(text)
            elif current_section == "overall" and stripped:
                # 整体评价的续行
                overall_comment += " " + stripped

        # 如果没有提取到整体评价，使用第一段
        if not overall_comment and ai_summary:
            paragraphs = ai_summary.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if para and len(para) > 10:
                    # 跳过标题行
                    if not any(kw in para for kw in ["整体评价", "亮点总结", "待改进点", "下一步建议"]):
                        overall_comment = para
                        break

    # 生成回退的整体评价
    if not overall_comment:
        avg_score = interview_score / answered_count if answered_count > 0 else 0
        if avg_score >= 80:
            overall_comment = "面试表现优秀，展现出扎实的专业能力和良好的综合素质。"
        elif avg_score >= 60:
            overall_comment = "面试表现良好，具备一定专业能力，仍有提升空间。"
        else:
            overall_comment = "面试表现有待提升，建议加强专业知识和表达能力。"

    # 构建建议映射
    for i, text in enumerate(suggestions_text[:5], 1):
        suggestions[str(i)] = text

    # 如果没有建议，生成基于分数的建议
    if not suggestions:
        avg_score = interview_score / answered_count if answered_count > 0 else 0
        if avg_score >= 80:
            suggestions["1"] = "继续保持当前的学习和工作状态，注重实战经验的积累。"
        elif avg_score >= 60:
            suggestions["1"] = "建议加强项目经验的总结和表达能力的训练。"
        else:
            suggestions["1"] = "建议系统学习相关技术知识，加强实际项目练习。"

    # 解析专业技能和发展潜力评分
    # 这些评分应该从 AI 总结中提取，如果没有则设为 null
    professional_score = None
    potential_score = None
    
    if ai_summary:
        lines = ai_summary.split("\n")
        for line in lines:
            stripped = line.strip()
            # 查找专业技能评分
            if "专业技能" in stripped and "评分" in stripped and ":" in stripped:
                try:
                    score_part = stripped.split(":", 1)[-1].strip()
                    # 尝试提取数字
                    import re
                    numbers = re.findall(r'\d+', score_part)
                    if numbers:
                        professional_score = int(numbers[0])
                except Exception:
                    pass
            # 查找发展潜力评分
            if "发展潜力" in stripped and "评分" in stripped and ":" in stripped:
                try:
                    score_part = stripped.split(":", 1)[-1].strip()
                    import re
                    numbers = re.findall(r'\d+', score_part)
                    if numbers:
                        potential_score = int(numbers[0])
                except Exception:
                    pass

    # 注意：如果 AI 总结中没有这两个评分，则设为 null，不进行估算

    # 保存 AI 总结原始文本
    interview_suggestions_text = "\n".join(suggestions_text) if suggestions_text else overall_comment

    # 更新快照中的最终报告数据
    await service.update_snapshot(session_id, {
        "status": "FINISHED",
        "total_score": total_score,
        "interview_score": interview_score,
        "resume_score": resume_score,
        "composite_score": (resume_score + interview_score) / 2 if interview_score > 0 else resume_score,
        "answered_count": answered_count,
        "professional_score": professional_score,
        "potential_score": potential_score,
        "interview_suggestions": suggestions,
        "interview_suggestions_text": interview_suggestions_text,
        "ai_summary": ai_summary,
        "review_feedback": {
            "overallComment": overall_comment,
            "highlights": highlights[:3],
            "improvementTips": improvement_tips[:3],
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    })

    # 更新面试状态为完成，同时保存面试分数
    await service.update_status(
        session_id, 
        "FINISHED",
        interview_score=interview_score,
        resume_score=resume_score,
    )

    # ========== 集成仪态评估（面试结束时自动调用）==========
    # 注意：即使没有仪态数据，也需要设置默认分数供雷达图展示
    demeanor_result = None
    default_demeanor_score = 0
    
    try:
        # 获取仪态数据
        demeanor_frames = snapshot.get("demeanor_frames", []) if snapshot else []
        demeanor_audio = snapshot.get("demeanor_audio_segments", []) if snapshot else []

        if demeanor_frames or demeanor_audio:
            from app.integrations.mediapipe import comprehensive_scorer
            from datetime import datetime as dt

            # 设置开始和结束时间
            start_time_str = snapshot.get("demeanor_stream_start_time") if snapshot else None
            start_time = None
            if start_time_str:
                try:
                    start_time = dt.fromisoformat(start_time_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            # 如果有帧数据，推送到跟踪器
            tracker = comprehensive_scorer.get_or_create_tracker(session_id)
            for frame in demeanor_frames:
                try:
                    tracker.append_video_frame(frame)
                except Exception:
                    pass

            for seg in demeanor_audio:
                try:
                    tracker.append_audio_segment(seg)
                except Exception:
                    pass

            # 执行最终评估
            end_time = dt.now(timezone.utc)
            report = await comprehensive_scorer.evaluate_comprehensive(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                qa_data={"answers": answers},
            )

            # 保存仪态报告
            report_dict = report.to_dict()
            await service.update_snapshot(session_id, {
                "demeanor_report": report_dict,
                "demeanor_score": report.demeanor_total_score,
                "demeanor_grade": report.demeanor_grade,
                "demeanor_evaluation_completed_at": end_time.isoformat(),
            })

            demeanor_result = {
                "demeanor_total_score": report.demeanor_total_score,
                "demeanor_grade": report.demeanor_grade,
                "head_pose_score": report.head_pose_score,
                "eye_contact_score": report.eye_contact_score,
                "expression_score": report.expression_score,
                "body_posture_score": report.body_posture_score,
                "speech_score": report.speech_score,
                "llm_overall_comment": report.llm_overall_comment,
                "llm_suggestions": report.llm_suggestions,
            }
            default_demeanor_score = report.demeanor_total_score

            logger.info(f"仪态评估完成: session_id={session_id}, score={report.demeanor_total_score}")
        else:
            # 没有仪态数据时，设置 null 让前端显示为空（不显示估算分数）
            default_demeanor_score = None
            
            # 保存空仪态数据标记
            await service.update_snapshot(session_id, {
                "demeanor_score": None,
                "demeanor_grade": None,
                "demeanor_note": "未采集实际仪态数据，请开启摄像头以获取仪态评估",
            })
            logger.info(f"仪态评估跳过（无数据）: session_id={session_id}")
    except Exception as e:
        logger.error(f"仪态评估失败: {e}")
        # 评估失败时也设置为 null
        default_demeanor_score = None
        await service.update_snapshot(session_id, {
            "demeanor_score": None,
            "demeanor_grade": None,
            "demeanor_note": "仪态评估失败，请确保摄像头正常工作",
        })

    response_data = {
        "sessionId": session_id,
        "status": "FINISHED",
        "interviewScore": interview_score,
        "totalScore": total_score,
    }

    # 合并仪态评估结果
    if demeanor_result:
        response_data["demeanorScore"] = demeanor_result["demeanor_total_score"]
        response_data["demeanorGrade"] = demeanor_result["demeanor_grade"]
        response_data["demeanorDetails"] = demeanor_result

    return {
        "code": 200,
        "message": "success",
        "data": response_data
    }


# 在 get_interview_record 之前添加分页查询接口
@router.get("/records")
async def list_interview_records(
    pageNum: int = Query(default=1, ge=1, alias="pageNum", description="当前页"),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试记录列表（分页）"""
    skip = (pageNum - 1) * pageSize
    items, total = await service.get_by_user_id(
        user_id=current_user.id,
        skip=skip,
        limit=pageSize,
    )

    # 状态中文映射
    status_map = {
        "INIT": "待开始",
        "IN_PROGRESS": "面试中",
        "ASKING": "提问中",
        "EVALUATING": "评估中",
        "FOLLOW_UP": "追问中",
        "COMPLETED": "已完成",
        "FINISHED": "已完成",
    }

    # 构建分页响应
    records = []
    for item in items:
        # 优先从 MongoDB 快照获取面试分数（对于历史数据）
        interview_score = item.interview_score or 0
        if interview_score == 0:
            snapshot = await service.get_snapshot(item.session_id)
            if snapshot:
                # 优先使用 interview_score（百分比形式）
                interview_score = snapshot.get("interview_score", 0)
                if interview_score == 0:
                    # 其次使用 total_score 转换为百分比
                    total_score = snapshot.get("total_score", 0)
                    questions = snapshot.get("questions", [])
                    total_possible = len(questions) * 20 if questions else 5 * 20
                    interview_score = int((total_score / total_possible) * 100) if total_possible > 0 else 0
                    if interview_score == 0:
                        # 最后从 answers 中计算
                        answers = snapshot.get("answers", [])
                        raw_score = sum(a.get("score", 0) for a in answers if a.get("score"))
                        if raw_score > 0:
                            interview_score = int((raw_score / total_possible) * 100) if total_possible > 0 else 0

        # 获取简历分数
        resume_score = item.resume_score or 0

        # 根据权重计算综合评分
        # 权重：内容专业度30% + 仪态专项20% + 语言表达20% + 简历15% + 原始面试15%
        snapshot = await service.get_snapshot(item.session_id)
        demeanor_report = snapshot.get("demeanor_report") if snapshot else None

        if demeanor_report:
            llm_content = demeanor_report.get("llm_content_score", 0) or 0  # 0-40分
            llm_posture = demeanor_report.get("llm_posture_score", 0) or 0  # 0-30分
            llm_speech = demeanor_report.get("llm_speech_score", 0) or 0  # 0-30分
            # 转换为100分制
            content_100 = (llm_content / 40) * 100 if llm_content > 0 else 0
            posture_100 = (llm_posture / 30) * 100 if llm_posture > 0 else 0
            speech_100 = (llm_speech / 30) * 100 if llm_speech > 0 else 0
            # 加权计算
            composite_score = (
                content_100 * 0.30 +
                posture_100 * 0.20 +
                speech_100 * 0.20 +
                resume_score * 0.15 +
                interview_score * 0.15
            )
            composite_score = int(round(composite_score))
        else:
            # 没有仪态数据时，使用简历和面试得分的加权平均
            if resume_score > 0 and interview_score > 0:
                composite_score = int((resume_score * 0.4 + interview_score * 0.6))
            elif interview_score > 0:
                composite_score = interview_score
            else:
                composite_score = resume_score

        # 格式化时长
        duration_str = ""
        if item.duration_seconds:
            minutes = item.duration_seconds // 60
            seconds = item.duration_seconds % 60
            duration_str = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

        # 格式化创建时间
        create_time_str = ""
        if item.create_time:
            create_time_str = item.create_time.strftime("%Y-%m-%d %H:%M")

        records.append({
            "id": item.id,
            "userId": item.user_id,
            "sessionId": item.session_id,
            "interviewDirection": item.interview_direction or "通用面试",
            "interviewStatus": item.interview_status,
            "statusText": status_map.get(item.interview_status, item.interview_status or "未知"),
            "resumeScore": resume_score,
            "interviewScore": interview_score,
            "compositeScore": composite_score,
            "questionCount": item.question_count or 0,
            "durationSeconds": item.duration_seconds,
            "durationText": duration_str,
            "startTime": item.start_time.isoformat() if item.start_time else None,
            "endTime": item.end_time.isoformat() if item.end_time else None,
            "createTime": item.create_time.isoformat() if item.create_time else None,
            "createTimeText": create_time_str,
        })

    return {
        "code": 200,
        "message": "success",
        "records": records,
        "total": total,
        "pageNum": pageNum,
        "pageSize": pageSize,
        "pages": (total + pageSize - 1) // pageSize if total > 0 else 0,
    }


@router.delete("/record/{session_id}")
async def delete_interview_record(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """删除面试记录"""
    success = await service.soft_delete(session_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试记录不存在或无权删除",
        )
    return {"code": 200, "message": "success"}


@router.get("/record/{session_id}")
async def get_interview_record(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试记录"""
    # 从快照中获取面试记录数据
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试记录不存在",
        )

    # 获取面试会话信息
    interview = await service.get_by_session_id(session_id)

    # 序列化快照
    serialized_snapshot = _serialize_snapshot(snapshot)

    # 构建报告数据
    answers = snapshot.get("answers", [])
    questions = snapshot.get("questions", [])

    # 计算面试分数
    total_score = sum(a.get("score", 0) for a in answers if a.get("score"))
    answered_count = len([a for a in answers if a.get("score") is not None])
    interview_score = total_score if answered_count > 0 else None

    # 简历分数
    resume_score = interview.resume_score if interview else snapshot.get("resume_score") or 0

    # 根据权重计算综合评分
    demeanor_report = snapshot.get("demeanor_report") if snapshot else None

    if demeanor_report:
        llm_content = demeanor_report.get("llm_content_score", 0) or 0
        llm_posture = demeanor_report.get("llm_posture_score", 0) or 0
        llm_speech = demeanor_report.get("llm_speech_score", 0) or 0
        content_100 = (llm_content / 40) * 100 if llm_content > 0 else 0
        posture_100 = (llm_posture / 30) * 100 if llm_posture > 0 else 0
        speech_100 = (llm_speech / 30) * 100 if llm_speech > 0 else 0
        composite_score = int(round(
            content_100 * 0.30 +
            posture_100 * 0.20 +
            speech_100 * 0.20 +
            resume_score * 0.15 +
            interview_score * 0.15
        ))
    else:
        composite_score = int((resume_score * 0.4 + interview_score * 0.6)) if resume_score > 0 and interview_score > 0 else (interview_score or resume_score)

    # 构建 QA 列表 - 只显示有实际回答的问答
    qa_reviews = []
    answered_question_numbers = set()

    for a in answers:
        q_number = a.get("question_number", "")
        is_follow_up = a.get("is_follow_up", False)

        if is_follow_up:
            parent_number = q_number.rsplit("-F", 1)[0] if "-F" in q_number else q_number
            qa_reviews.append({
                "questionNumber": q_number,
                "question": a.get("question_content", "") or a.get("follow_up_question", ""),
                "answer": a.get("answer_content", ""),
                "score": a.get("score"),
                "feedback": a.get("evaluation", "") or a.get("feedback", ""),
                "isFollowUp": True,
                "followUpCount": None,
            })
        else:
            q_content = ""
            for q in questions:
                if q.get("number") == q_number:
                    q_content = q.get("content", "")
                    break
            if not q_content:
                q_content = a.get("question_content", "")

            qa_reviews.append({
                "questionNumber": q_number,
                "question": q_content,
                "answer": a.get("answer_content", ""),
                "score": a.get("score"),
                "feedback": a.get("evaluation", "") or a.get("feedback", ""),
                "isFollowUp": False,
                "followUpCount": len([x for x in answers if x.get("question_number") == q_number and x.get("is_follow_up")]),
            })
            answered_question_numbers.add(q_number)

    # 按问题编号排序
    def sort_key(item):
        qn = item.get("questionNumber", "")
        try:
            if "-F" in qn:
                qn = qn.split("-F")[0]
            return int(qn)
        except:
            return 0

    qa_reviews.sort(key=sort_key)

    # 构建雷达图数据
    # 注意：interview_score 是总分，需要转换为平均分（满分100）
    avg_interview_score = interview_score / answered_count if answered_count > 0 else 0
    
    # 从快照读取各维度分数（可能为 None）
    demeanor_score = snapshot.get("demeanor_score")
    professional_score = snapshot.get("professional_score")
    potential_score = snapshot.get("potential_score")
    
    radar_points = [
        {"label": "简历评估", "value": resume_score},
        {"label": "面试表现", "value": int(avg_interview_score)},
        {"label": "仪态表达", "value": int(demeanor_score) if demeanor_score is not None else None},
        {"label": "专业技能", "value": int(professional_score) if professional_score is not None else None},
        {"label": "发展潜力", "value": int(potential_score) if potential_score is not None else None},
    ]

    # 获取面试建议
    interview_suggestions = snapshot.get("interview_suggestions", {})
    if isinstance(interview_suggestions, dict):
        sorted_suggestions = dict(sorted(interview_suggestions.items()))
        suggestions_text = "\n".join(f"{k}. {v}" for k, v in sorted_suggestions.items() if v)
    else:
        suggestions_text = str(interview_suggestions) if interview_suggestions else ""

    # 获取简历分析
    resume_analysis = snapshot.get("resume_analysis", {})

    # 状态中文映射
    status_map = {
        "INIT": "待开始",
        "IN_PROGRESS": "面试中",
        "ASKING": "提问中",
        "EVALUATING": "评估中",
        "FOLLOW_UP": "追问中",
        "COMPLETED": "已完成",
        "FINISHED": "已完成",
    }
    interview_status = interview.interview_status if interview else snapshot.get("status")
    status_text = status_map.get(interview_status, interview_status or "未知")

    # 格式化时长
    duration_seconds = interview.duration_seconds if interview else None
    duration_text = ""
    if duration_seconds:
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        duration_text = f"{minutes}分{seconds}秒" if minutes > 0 else f"{seconds}秒"

    return {
        "code": 200,
        "message": "success",
        "data": {
            **serialized_snapshot,
            "sessionId": session_id,
            "interviewDirection": interview.interview_direction if interview else snapshot.get("interview_direction") or "通用面试",
            "interviewStatus": interview_status,
            "statusText": status_text,
            "resumeScore": resume_score,
            "interviewScore": interview_score,
            "totalScore": total_score,
            "compositeScore": composite_score,
            "finalScore": total_score,
            "questionCount": len(questions),
            "answeredCount": answered_count,
            "durationSeconds": duration_seconds,
            "durationText": duration_text,
            "resumeAnalysis": resume_analysis,
            "radarChart": {
                "resumeScore": resume_score,
                "interviewPerformance": interview_score,
                "radarMetrics": radar_points,
            },
            "radarPoints": radar_points,
            "qaReviews": qa_reviews,
            "questionAnswers": qa_reviews,
            "interviewQaList": qa_reviews,
            "interviewSuggestions": suggestions_text,
            "interviewSuggestionsMap": interview_suggestions if isinstance(interview_suggestions, dict) else {},
            "reviewFeedback": snapshot.get("review_feedback") or snapshot.get("reviewFeedback") or {
                "overallComment": snapshot.get("overall_comment", ""),
                "highlights": snapshot.get("highlights", []),
                "improvementTips": snapshot.get("improvement_tips", []),
            },
            "startTime": interview.start_time.isoformat() if interview and interview.start_time else None,
            "endTime": interview.end_time.isoformat() if interview and interview.end_time else None,
        }
    }


@router.post("/record")
async def create_interview_record(
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """创建面试记录（占位接口）"""
    return {
        "code": 200,
        "message": "success",
        "data": None,
    }


@router.post("/record/save-from-redis/{session_id}")
async def save_interview_record_from_redis(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """从 Redis 保存面试记录"""
    # 从快照中获取面试记录数据
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试记录不存在",
        )
    # 这里可以添加保存到数据库的逻辑
    return {
        "code": 200,
        "message": "success",
        "data": _serialize_snapshot(snapshot),
    }


# ========== 答案提交接口 ==========

from pydantic import BaseModel


class AnswerRequest(BaseModel):
    """答案提交请求"""
    question_number: str
    answer_content: str
    request_id: Optional[str] = None


class AnswerJsonRequest(BaseModel):
    """JSON 格式答案提交请求"""
    questionNumber: str
    answerContent: str
    requestId: Optional[str] = None


@router.post("/sessions/{session_id}/interview/answer")
async def submit_interview_answer(
    session_id: str,
    request: AnswerRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """提交面试答案（表单格式）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    try:
        result = await service.submit_answer(
            session_id=session_id,
            question_number=request.question_number,
            answer_content=request.answer_content,
        )

        # 保存消息
        await service.save_message(
            session_id=session_id,
            role="user",
            content=request.answer_content,
            metadata={"question_number": request.question_number, "score": result.get("score")},
        )

        # 返回符合前端期望的格式
        return {
            "code": 200,
            "message": "success",
            "data": {
                "isSuccess": result.get("is_success", True),
                "questionNumber": result.get("question_number"),
                "questionContent": result.get("question_content"),
                "score": result.get("score", 0),
                "totalScore": result.get("total_score", 0),
                "feedback": result.get("feedback", ""),
                "nextQuestion": result.get("next_question"),
                "nextQuestionNumber": result.get("next_question_number"),
                "isFollowUp": result.get("is_follow_up", False),
                "followUpCount": result.get("current_follow_up_count", 0),
                "finished": result.get("finished", False),
            },
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/sessions/{session_id}/interview/answer-json")
async def submit_interview_answer_json(
    session_id: str,
    request: AnswerJsonRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """提交面试答案（JSON 格式，与 Java 后端兼容）"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    try:
        # 使用答案处理管道
        from app.application.interview.answer_pipeline import InterviewAnswerPipeline
        pipeline = InterviewAnswerPipeline(service)
        result = await pipeline.execute(
            session_id=session_id,
            request_id=request.requestId,
            question_number=request.questionNumber,
            answer_content=request.answerContent,
        )

        # 保存用户消息
        await service.save_message(
            session_id=session_id,
            role="user",
            content=request.answerContent,
            metadata={
                "question_number": request.questionNumber,
                "score": result.score,
            },
        )

        # 返回符合前端期望的格式
        return {
            "code": 200,
            "message": "success" if result.is_success else "failed",
            "isSuccess": result.is_success,
            "errorMessage": result.error_message,
            "data": {
                "isSuccess": result.is_success,
                "questionNumber": result.question_number,
                "questionContent": result.question_content,
                "score": result.score,
                "totalScore": result.total_score,
                "feedback": result.feedback,
                "nextQuestion": result.next_question,
                "nextQuestionNumber": result.next_question_number,
                "isFollowUp": result.is_follow_up,
                "followUpCount": result.follow_up_count,
                "finished": result.finished,
            },
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/sessions/{session_id}/interview/follow-up")
async def generate_interview_follow_up(
    session_id: str,
    request: AnswerJsonRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """生成追问"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    try:
        follow_up = await service.generate_follow_up(
            session_id=session_id,
            question_number=request.questionNumber,
            answer_content=request.answerContent,
        )

        if follow_up is None:
            return {
                "code": 200,
                "message": "追问次数已达上限",
                "data": {
                    "hasFollowUp": False,
                    "followUpContent": None,
                }
            }

        # 保存追问消息
        await service.save_message(
            session_id=session_id,
            role="assistant",
            content=follow_up,
            metadata={"question_number": request.questionNumber, "type": "follow_up"},
        )

        return {
            "code": 200,
            "message": "success",
            "data": {
                "hasFollowUp": True,
                "followUpContent": follow_up,
                "followUpNumber": f"{request.questionNumber}_f1",
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sessions/{session_id}/radar-chart")
async def get_interview_radar_chart(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """获取面试雷达图数据"""
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试会话不存在",
        )
    if interview.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该面试会话",
        )

    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="面试快照不存在",
        )

    answers = snapshot.get("answers", [])

    # 计算各维度得分
    dimensions = {
        "准确性": 0,
        "完整性": 0,
        "技术深度": 0,
        "表达清晰度": 0,
        "项目经验": 0,
    }

    for answer in answers:
        details = answer.get("details", {})
        dimensions["准确性"] += details.get("accuracy", 0)
        dimensions["完整性"] += details.get("completeness", 0)
        dimensions["技术深度"] += details.get("depth", 0)
        dimensions["表达清晰度"] += details.get("clarity", 0)
        dimensions["项目经验"] += details.get("relevance", 0)

    count = len(answers) if answers else 1
    radar_data = {k: round(v / count, 1) for k, v in dimensions.items()}

    return {
        "code": 200,
        "message": "success",
        "data": {
            "dimensions": list(radar_data.keys()),
            "scores": list(radar_data.values()),
            "totalScore": snapshot.get("total_score", 0),
            "averageScore": round(snapshot.get("total_score", 0) / count, 1) if count > 0 else 0,
            "questionCount": count,
        }
    }


# ========== 增强版仪态分析 API ==========

from pydantic import BaseModel
from datetime import datetime


class DemeanorFrameUploadRequest(BaseModel):
    """仪态帧数据上传请求"""
    timestamp_ms: int = 0
    frame_data: dict = {}  # VideoFrameData


class DemeanorAudioUploadRequest(BaseModel):
    """仪态音频数据上传请求"""
    timestamp_ms: int = 0
    audio_segment: dict = {}  # AudioFrameData


class DemeanorStreamInitRequest(BaseModel):
    """仪态流初始化请求"""
    start_time: Optional[str] = None  # ISO 格式时间戳


class DemeanorFinalEvaluateRequest(BaseModel):
    """仪态最终评估请求"""
    end_time: Optional[str] = None  # ISO 格式时间戳


@router.post("/sessions/{session_id}/demeanor/stream/init")
async def demeanor_stream_init(
    session_id: str,
    request: DemeanorStreamInitRequest,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    仪态流分析 - 初始化会话

    前端在面试开始时调用此接口，初始化仪态跟踪器。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 获取或创建跟踪器
    from app.integrations.mediapipe import comprehensive_scorer, create_tracker
    tracker = comprehensive_scorer.get_or_create_tracker(session_id)

    # 设置开始时间
    if request.start_time:
        try:
            start_dt = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
            tracker._start_time_ms = int(start_dt.timestamp() * 1000)
        except Exception:
            pass

    # 保存初始化状态到快照
    await service.save_snapshot(session_id, {
        "demeanor_stream_active": True,
        "demeanor_stream_start_time": request.start_time or datetime.now(timezone.utc).isoformat(),
        "demeanor_frames": [],
        "demeanor_audio_segments": [],
    })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "session_id": session_id,
            "stream_active": True,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
        }
    }


@router.post("/sessions/{session_id}/demeanor/stream/frame")
async def demeanor_stream_upload_frame(
    session_id: str,
    timestamp_ms: int = Query(default=0, description="时间戳（毫秒）"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    仪态流分析 - 上传视频帧

    前端实时推送视频帧数据到此接口。
    接收 base64 编码的图片数据，返回实时分析结果。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 读取原始请求体获取图片数据
    import base64
    try:
        body = await import_module("fastapi").Request.form()
        frame_file = body.get("frame")
        if frame_file:
            image_bytes = await frame_file.read()
            # 解码图片
            import numpy as np
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                raise HTTPException(status_code=400, detail="无法解析图片数据")
        else:
            raise HTTPException(status_code=400, detail="未提供 frame 字段")
    except Exception as e:
        logger.error(f"读取帧数据失败: {e}")
        raise HTTPException(status_code=400, detail=f"读取帧数据失败: {str(e)}")

    # 调用增强版视频分析器
    from app.integrations.mediapipe import enhanced_video_analyzer
    frame_result = enhanced_video_analyzer.analyze_frame(frame, timestamp_ms=timestamp_ms)

    if frame_result is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "face_detected": False,
                "timestamp_ms": timestamp_ms,
            }
        }

    # 转换为 dict
    frame_dict = {
        "timestamp_ms": timestamp_ms,
        "face_detected": True,
        "face_count": 1,
        "confidence": frame_result.confidence,
        "face_blur_score": frame_result.face_blur_score,
        "face_size_ratio": frame_result.face_size_ratio,
    }

    if frame_result.head_pose:
        frame_dict["head_pose"] = {
            "yaw": frame_result.head_pose.yaw,
            "pitch": frame_result.head_pose.pitch,
            "roll": frame_result.head_pose.roll,
            "is_stable": frame_result.head_pose.is_stable,
        }
    if frame_result.eye_state:
        frame_dict["eye_state"] = {
            "left_eye_openness": frame_result.eye_state.left_eye_openness,
            "right_eye_openness": frame_result.eye_state.right_eye_openness,
            "avg_eye_openness": frame_result.eye_state.avg_eye_openness,
            "is_blinking": frame_result.eye_state.is_blinking,
            "gaze_direction": frame_result.eye_state.gaze_direction,
            "gaze_offset_x": frame_result.eye_state.gaze_offset_x,
            "gaze_offset_y": frame_result.eye_state.gaze_offset_y,
        }
    if frame_result.expression:
        frame_dict["expression"] = {
            "happiness": frame_result.expression.happiness,
            "sadness": frame_result.expression.sadness,
            "anger": frame_result.expression.anger,
            "surprise": frame_result.expression.surprise,
            "neutral": frame_result.expression.neutral,
            "dominant": frame_result.expression.dominant,
            "is_negative": frame_result.expression.is_negative,
        }
    if frame_result.body_posture:
        frame_dict["body_posture"] = {
            "is_sitting_up": frame_result.body_posture.is_sitting_up,
            "arm_crossed": frame_result.body_posture.arm_crossed,
            "body_sway": frame_result.body_posture.body_sway,
        }

    # 推送到跟踪器
    from app.integrations.mediapipe import comprehensive_scorer
    tracker = comprehensive_scorer.get_or_create_tracker(session_id)
    summary = tracker.append_video_frame(frame_dict)

    # 实时保存到 MongoDB（可选，减少写入频率可以批量处理）
    snapshot = await service.get_snapshot(session_id)
    if snapshot:
        frames = snapshot.get("demeanor_frames", [])
        frames.append(frame_dict)
        # 只保留最近 1000 帧
        if len(frames) > 1000:
            frames = frames[-1000:]
        await service.update_snapshot(session_id, {"demeanor_frames": frames})

    return {
        "code": 200,
        "message": "success",
        "data": {
            **frame_dict,
            "realtime_summary": summary,
        }
    }


@router.post("/sessions/{session_id}/demeanor/stream/audio")
async def demeanor_stream_upload_audio(
    session_id: str,
    timestamp_ms: int = Query(default=0, description="时间戳（毫秒）"),
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    仪态流分析 - 上传音频片段

    前端实时推送音频片段数据到此接口。
    接收 Whisper 识别结果（文本、语速等）。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 读取请求体
    try:
        body = await import_module("fastapi").Request.json()
        audio_segment = body.get("audio_segment", {})
    except Exception:
        audio_segment = {}

    # 转换为 dict
    segment_dict = {
        "timestamp_ms": timestamp_ms,
        **audio_segment,
    }

    # 推送到跟踪器
    from app.integrations.mediapipe import comprehensive_scorer
    tracker = comprehensive_scorer.get_or_create_tracker(session_id)
    summary = tracker.append_audio_segment(segment_dict)

    # 实时保存到 MongoDB
    snapshot = await service.get_snapshot(session_id)
    if snapshot:
        segments = snapshot.get("demeanor_audio_segments", [])
        segments.append(segment_dict)
        if len(segments) > 500:
            segments = segments[-500:]
        await service.update_snapshot(session_id, {"demeanor_audio_segments": segments})

    return {
        "code": 200,
        "message": "success",
        "data": {
            **segment_dict,
            "realtime_summary": summary,
        }
    }


@router.post("/sessions/{session_id}/demeanor/stream/batch-frames")
async def demeanor_stream_batch_frames(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    仪态流分析 - 批量上传视频帧

    前端可以一次性上传多帧数据，减少网络请求次数。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 读取请求体
    try:
        body = await import_module("fastapi").Request.json()
        frames = body.get("frames", [])
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求数据")

    if not frames:
        return {
            "code": 200,
            "message": "success",
            "data": {"processed": 0}
        }

    # 批量处理
    from app.integrations.mediapipe import comprehensive_scorer
    tracker = comprehensive_scorer.get_or_create_tracker(session_id)

    processed = 0
    results = []
    for frame_dict in frames:
        try:
            summary = tracker.append_video_frame(frame_dict)
            results.append({
                "timestamp_ms": frame_dict.get("timestamp_ms", 0),
                "face_detected": frame_dict.get("face_detected", False),
                "summary": summary,
            })
            processed += 1
        except Exception as e:
            logger.debug(f"处理帧失败: {e}")

    # 更新 MongoDB
    snapshot = await service.get_snapshot(session_id)
    if snapshot:
        existing_frames = snapshot.get("demeanor_frames", [])
        existing_frames.extend([f for f in frames if f.get("face_detected")])
        if len(existing_frames) > 1000:
            existing_frames = existing_frames[-1000:]
        await service.update_snapshot(session_id, {"demeanor_frames": existing_frames})

    return {
        "code": 200,
        "message": "success",
        "data": {
            "processed": processed,
            "total_frames": processed,
            "results": results,
        }
    }


@router.post("/sessions/{session_id}/demeanor/evaluate-final")
async def demeanor_evaluate_final(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    仪态流分析 - 最终评估

    面试结束时调用此接口，汇总所有帧数据，计算综合评分，调用大模型生成评语。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 获取快照数据
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="无仪态数据")

    # 获取时间范围
    start_time_str = snapshot.get("demeanor_stream_start_time")
    start_time = None
    end_time = datetime.now(timezone.utc)
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except Exception:
            start_time = None

    # 获取问答数据
    qa_data = {
        "answers": snapshot.get("answers", []),
    }

    # 调用综合评分器
    from app.integrations.mediapipe import comprehensive_scorer
    report = await comprehensive_scorer.evaluate_comprehensive(
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
        qa_data=qa_data,
    )

    # 保存评估结果到快照
    report_dict = report.to_dict()
    await service.update_snapshot(session_id, {
        "demeanor_report": report_dict,
        "demeanor_score": report.demeanor_total_score,
        "demeanor_grade": report.demeanor_grade,
        "demeanor_evaluation_completed_at": end_time.isoformat(),
    })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "session_id": session_id,
            "total_duration_ms": report.total_duration_ms,
            "valid_video_frames": report.valid_video_frames,
            # 评分
            "head_pose_score": report.head_pose_score,
            "eye_contact_score": report.eye_contact_score,
            "expression_score": report.expression_score,
            "body_posture_score": report.body_posture_score,
            "speech_score": report.speech_score,
            "demeanor_total_score": report.demeanor_total_score,
            "demeanor_grade": report.demeanor_grade,
            # ========== 大模型详细评分（新格式）==========
            "llm_posture_score": report.llm_posture_score,
            "llm_speech_score": report.llm_speech_score,
            "llm_content_score": report.llm_content_score,
            "llm_total_score": report.llm_total_score,
            # ========== 分项问题列表 ==========
            "llm_posture_issues": report.llm_posture_issues,
            "llm_speech_issues": report.llm_speech_issues,
            "llm_content_issues": report.llm_content_issues,
            # ========== 分项改进建议 ==========
            "llm_posture_suggestions": report.llm_posture_suggestions,
            "llm_speech_suggestions": report.llm_speech_suggestions,
            "llm_content_suggestions": report.llm_content_suggestions,
            # 统计摘要
            "head_pose_stats": {
                "stability_rate": report.head_pose_stats.stability_rate if report.head_pose_stats else 0,
                "total_looking_down_ms": report.head_pose_stats.total_looking_down_ms if report.head_pose_stats else 0,
                "turning_left_count": report.head_pose_stats.turning_left_count if report.head_pose_stats else 0,
                "turning_right_count": report.head_pose_stats.turning_right_count if report.head_pose_stats else 0,
            },
            "eye_stats": {
                "blink_frequency": report.eye_stats.blink_frequency if report.eye_stats else 0,
                "total_blinks": report.eye_stats.total_blinks if report.eye_stats else 0,
            },
            "expression_stats": {
                "dominant_expression": report.expression_stats.dominant_expression if report.expression_stats else "neutral",
                "negative_ratio": report.expression_stats.negative_ratio if report.expression_stats else 0,
            },
            # LLM 评语
            "llm_overall_comment": report.llm_overall_comment,
            "llm_strengths": report.llm_strengths,
            "llm_weaknesses": report.llm_weaknesses,
            "llm_suggestions": report.llm_suggestions,
            # 完整报告
            "full_report": report_dict,
        }
    }


@router.get("/sessions/{session_id}/demeanor/report")
async def demeanor_get_report(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    获取仪态评估报告

    面试结束后，前端可以调用此接口获取完整的仪态评估报告。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 获取快照数据
    snapshot = await service.get_snapshot(session_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="无仪态数据")

    report = snapshot.get("demeanor_report")
    if not report:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "available": False,
                "message": "仪态评估报告尚未生成，请先调用 /demeanor/evaluate-final",
            }
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "available": True,
            "session_id": session_id,
            "report": report,
        }
    }


@router.post("/sessions/{session_id}/demeanor/analyze-whisper")
async def demeanor_analyze_whisper_result(
    session_id: str,
    service: InterviewService = Depends(get_interview_service),
    current_user: User = Depends(get_current_user),
):
    """
    分析 Whisper 语音识别结果

    前端上传 Whisper 识别结果，后端分析语速、停顿、卡顿等指标。
    """
    interview = await service.get_by_session_id(session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该面试会话")

    # 读取请求体
    try:
        body = await import_module("fastapi").Request.json()
        whisper_result = body.get("whisper_result", {})
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求数据")

    if not whisper_result.get("text"):
        return {
            "code": 200,
            "message": "success",
            "data": {"has_audio": False}
        }

    # 调用增强版音频分析器
    from app.integrations.mediapipe import enhanced_audio_analyzer
    result = enhanced_audio_analyzer.analyze_from_whisper_result(whisper_result)

    # 评估语音质量
    quality = enhanced_audio_analyzer.estimate_speech_quality(result)
    feedback = enhanced_audio_analyzer.get_talking_speed_feedback(result)

    # 保存到快照
    await service.update_snapshot(session_id, {
        "audio_analysis_result": {
            "total_duration_ms": result.total_duration_ms,
            "speech_duration_ms": result.speech_duration_ms,
            "avg_speaking_rate": result.avg_speaking_rate,
            "total_pauses": result.total_pauses,
            "total_hesitations": result.total_hesitations,
            "silence_ratio": result.silence_ratio,
        },
        "audio_quality_score": quality["score"],
    })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "session_id": session_id,
            # 基础统计
            "total_duration_ms": result.total_duration_ms,
            "speech_duration_ms": result.speech_duration_ms,
            "silence_duration_ms": result.silence_duration_ms,
            # 语速
            "avg_speaking_rate": result.avg_speaking_rate,
            "min_speaking_rate": result.min_speaking_rate,
            "max_speaking_rate": result.max_speaking_rate,
            # 停顿
            "total_pauses": result.total_pauses,
            "avg_pause_duration_ms": result.avg_pause_duration_ms,
            "pause_segments": result.pause_segments[:10],  # 只返回前10个
            # 卡顿
            "total_hesitations": result.total_hesitations,
            "total_hesitation_duration_ms": result.total_hesitation_duration_ms,
            "hesitation_segments": result.hesitation_segments,
            # 静音
            "long_silences": result.long_silences,
            "silence_ratio": result.silence_ratio,
            # 质量评估
            "quality_score": quality,
            "speed_feedback": feedback,
        }
    }


def import_module(name):
    """安全导入模块"""
    import importlib
    return importlib.import_module(name)
