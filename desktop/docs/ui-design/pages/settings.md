# Settings Page Design

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header: 系统设置                                │
├─────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────────────────────────┐  │
│  │ 设置分类  │ │ 设置内容                      │  │
│  │          │ │                              │  │
│  │ ● 模型    │ │ 模型提供商                    │  │
│  │ ● 知识库  │ │ ┌──────────────────────┐    │  │
│  │ ● 用户    │ │ │ MIMO    [已连接] ●   │    │  │
│  │          │ │ │ MiniMax [已连接] ●   │    │  │
│  │          │ │ │ Ollama  [未配置] ○   │    │  │
│  │          │ │ └──────────────────────┘    │  │
│  │          │ │                              │  │
│  │          │ │ API密钥管理                  │  │
│  │          │ │ ┌──────────────────────┐    │  │
│  │          │ │ │ MIMO API Key: ****   │    │  │
│  │          │ │ │ [验证] [删除]         │    │  │
│  │          │ │ └──────────────────────┘    │  │
│  │          │ │                              │  │
│  │          │ │ 知识库存储                   │  │
│  │          │ │ 本地存储: 2.3 GB             │  │
│  │          │ │ [清理缓存] [导出数据]         │  │
│  └──────────┘ └──────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Components

- `SettingsNav.vue` — settings category navigation
- `ModelProviderSettings.vue` — provider connection status
- `ApiKeyManager.vue` — API key management
- `KnowledgeStorage.vue` — storage usage and management
- `UserProfile.vue` — user profile settings

## Mock Data

```typescript
providers: [
  { name: 'MIMO', status: 'connected', model: 'mimo-7b' },
  { name: 'MiniMax', status: 'connected', model: 'minimax-text' },
  { name: 'Ollama', status: 'disconnected', model: null }
]
storage: { used: 2.3, unit: 'GB', available: 47.7 }
```
