import { useCallback, useEffect, useState } from "react";
import { Settings, Pencil, Trash2, Plus, ToggleLeft, ToggleRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AiProperty, CreateAiModelParams, UpdateAiModelParams } from "@/types/ai";
import { aiService } from "@/services/aiService";
import { useToast } from "@/hooks/useToast";

const AI_TYPES = [
  { value: "openai", label: "OpenAI / 兼容 OpenAI 接口" },
  { value: "doubao", label: "豆包" },
  { value: "spark", label: "讯飞星火" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "other", label: "其他" },
];

interface FormData {
  aiName: string;
  aiType: string;
  apiKey: string;
  apiSecret: string;
  apiUrl: string;
  modelName: string;
  maxTokens: string;
  temperature: string;
  systemPrompt: string;
  isEnabled: number;
}

const initialFormData: FormData = {
  aiName: "",
  aiType: "openai",
  apiKey: "",
  apiSecret: "",
  apiUrl: "",
  modelName: "",
  maxTokens: "4096",
  temperature: "0.7",
  systemPrompt: "",
  isEnabled: 1,
};

export default function ModelManagePage() {
  const [models, setModels] = useState<AiProperty[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const { toast, ToastContainer } = useToast();

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const res = await aiService.getAiProperties();
      setModels(res.records);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleOpenCreate = () => {
    setEditingId(null);
    setFormData(initialFormData);
    setDialogOpen(true);
  };

  const handleOpenEdit = (model: AiProperty) => {
    setEditingId(model.id);
    setFormData({
      aiName: model.aiName || "",
      aiType: model.aiType || "openai",
      apiKey: "",
      apiSecret: "",
      apiUrl: model.apiUrl || "",
      modelName: model.modelName || "",
      maxTokens: model.maxTokens?.toString() || "4096",
      temperature: model.temperature?.toString() || "0.7",
      systemPrompt: model.systemPrompt || "",
      isEnabled: model.isEnabled ?? 1,
    });
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingId(null);
    setFormData(initialFormData);
  };

  const handleInputChange = (field: keyof FormData, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!formData.aiName.trim()) {
      toast.error("请输入模型名称");
      return;
    }
    if (!formData.modelName.trim()) {
      toast.error("请输入模型名称");
      return;
    }

    try {
      setSaving(true);
      const data = {
        aiName: formData.aiName.trim(),
        aiType: formData.aiType,
        apiKey: formData.apiKey || undefined,
        apiSecret: formData.apiSecret || undefined,
        apiUrl: formData.apiUrl || undefined,
        modelName: formData.modelName.trim(),
        maxTokens: formData.maxTokens ? parseInt(formData.maxTokens) : undefined,
        temperature: formData.temperature ? parseFloat(formData.temperature) : undefined,
        systemPrompt: formData.systemPrompt || undefined,
        isEnabled: formData.isEnabled,
      };

      if (editingId) {
        await aiService.updateAiModel({ ...data, id: editingId } as UpdateAiModelParams);
        toast.success("模型更新成功");
      } else {
        await aiService.createAiModel(data as CreateAiModelParams);
        toast.success("模型创建成功");
      }

      handleCloseDialog();
      fetchModels();
    } catch (error) {
      toast.error(editingId ? "更新失败" : "创建失败");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingId) return;
    try {
      setSaving(true);
      await aiService.deleteAiModel(deletingId);
      toast.success("删除成功");
      setDeleteDialogOpen(false);
      setDeletingId(null);
      fetchModels();
    } catch (error) {
      toast.error("删除失败");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async (model: AiProperty) => {
    const newStatus = model.isEnabled === 1 ? 0 : 1;
    try {
      await aiService.toggleAiModelStatus(model.id, newStatus);
      toast.success(newStatus === 1 ? "已启用" : "已禁用");
      fetchModels();
    } catch (error) {
      toast.error("状态更新失败");
      console.error(error);
    }
  };

  const getAiTypeLabel = (type: string) => {
    return AI_TYPES.find((t) => t.value === type)?.label || type;
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-indigo-100 p-2">
              <Settings className="h-6 w-6 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">AI 模型管理</h1>
              <p className="text-sm text-slate-500">管理对话使用的 AI 模型配置</p>
            </div>
          </div>
        </div>

        <div className="mb-4 flex justify-end">
          <Button onClick={handleOpenCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            添加模型
          </Button>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {models.map((model) => (
              <Card key={model.id} className={model.isEnabled === 0 ? "opacity-60" : ""}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg">{model.aiName}</CardTitle>
                      <p className="mt-1 text-sm text-slate-500">{getAiTypeLabel(model.aiType || "")}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleToggleStatus(model)}
                        title={model.isEnabled === 1 ? "禁用" : "启用"}
                      >
                        {model.isEnabled === 1 ? (
                          <ToggleRight className="h-5 w-5 text-green-600" />
                        ) : (
                          <ToggleLeft className="h-5 w-5 text-slate-400" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenEdit(model)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          setDeletingId(model.id);
                          setDeleteDialogOpen(true);
                        }}
                        className="text-red-500 hover:text-red-600 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">模型:</span>
                    <span className="font-medium text-slate-700">{model.modelName || "-"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">API 地址:</span>
                    <span className="max-w-[200px] truncate font-medium text-slate-700">
                      {model.apiUrl || "-"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">最大 Token:</span>
                    <span className="text-slate-700">{model.maxTokens || "-"}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
            {models.length === 0 && (
              <div className="col-span-2 flex h-48 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white">
                <div className="text-center text-slate-500">
                  <Settings className="mx-auto mb-2 h-8 w-8 text-slate-300" />
                  <p>暂无模型配置</p>
                  <p className="text-sm">点击上方按钮添加第一个 AI 模型</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>{editingId ? "编辑模型" : "添加模型"}</DialogTitle>
            <DialogDescription>
              {editingId ? "修改模型配置信息" : "填写模型的基本信息和 API 配置"}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="aiName">模型名称 *</Label>
              <Input
                id="aiName"
                placeholder="例如：硅基流动 DeepSeek V4"
                value={formData.aiName}
                onChange={(e) => handleInputChange("aiName", e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="aiType">模型类型</Label>
              <Select value={formData.aiType} onValueChange={(v) => handleInputChange("aiType", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="选择类型" />
                </SelectTrigger>
                <SelectContent>
                  {AI_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="apiKey">API Key</Label>
              <Input
                id="apiKey"
                type="password"
                placeholder={editingId ? "不修改请留空" : "输入 API Key"}
                value={formData.apiKey}
                onChange={(e) => handleInputChange("apiKey", e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="apiUrl">API 地址</Label>
              <Input
                id="apiUrl"
                placeholder="例如：https://api.siliconflow.cn/v1"
                value={formData.apiUrl}
                onChange={(e) => handleInputChange("apiUrl", e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="modelName">模型标识 *</Label>
              <Input
                id="modelName"
                placeholder="例如：deepseek-ai/DeepSeek-V4-Pro"
                value={formData.modelName}
                onChange={(e) => handleInputChange("modelName", e.target.value)}
              />
              <p className="text-xs text-slate-500">
                在硅基流动等平台查看模型的完整标识符
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="maxTokens">最大 Token</Label>
                <Input
                  id="maxTokens"
                  type="number"
                  placeholder="4096"
                  value={formData.maxTokens}
                  onChange={(e) => handleInputChange("maxTokens", e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="temperature">温度参数</Label>
                <Input
                  id="temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  placeholder="0.7"
                  value={formData.temperature}
                  onChange={(e) => handleInputChange("temperature", e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="systemPrompt">系统提示词</Label>
              <Textarea
                id="systemPrompt"
                placeholder="设置 AI 的角色和行为规则..."
                rows={4}
                value={formData.systemPrompt}
                onChange={(e) => handleInputChange("systemPrompt", e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingId ? "保存" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除这个模型配置吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ToastContainer />
    </div>
  );
}
