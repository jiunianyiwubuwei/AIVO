import service from "@/lib/request";

export interface CreateAgentParams {
  agentName: string;
  aiMode?: string;
  aiPropertiesId?: number;
  apiFlowId?: string;
  apiKey?: string;
  apiSecret?: string;
  systemPrompt?: string;
  tagCodes?: number[];
}

export interface UpdateAgentParams extends CreateAgentParams {
  id: number;
}

export interface AgentProperty {
  id: number;
  agentName: string;
  apiFlowId?: string;
  aiMode?: string;
  aiPropertiesId?: number;
  systemPrompt?: string;
  aiModelName?: string;
  tags?: Array<{ code: number; name: string; color?: string }>;
}

export interface PageResult<T> {
  records: T[];
  total: number;
  current: number;
  pages: number;
  size: number;
}

export interface AiModelOption {
  id: number;
  aiName: string;
  aiType: string;
  modelName: string;
  isEnabled: number;
}

export interface PageRequest {
  pageNum?: number;
  pageSize?: number;
}

export const agentService = {
  getAgentProperties: (params?: PageRequest) => {
    return service.get<PageResult<AgentProperty>>("/xunzhi/v1/agent-properties", { params });
  },

  getAvailableModels: () => {
    return service.get<AiModelOption[]>("/xunzhi/v1/agent-properties/available-models");
  },

  createAgent: (data: CreateAgentParams) => {
    return service.post("/xunzhi/v1/agent-properties", data);
  },

  updateAgent: (id: number, data: UpdateAgentParams) => {
    return service.put("/xunzhi/v1/agent-properties", { ...data, id });
  },

  deleteAgent: (id: number) => {
    return service.delete(`/xunzhi/v1/agent-properties/${id}`);
  },
};
