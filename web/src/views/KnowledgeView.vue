<template>
  <div class="knowledge-view">
    <el-tabs v-model="activeTab" type="border-card" class="knowledge-tabs">
      <el-tab-pane label="知识库" name="knowledge">
    <!-- ===== 动态分类标签云 ===== -->
    <el-card v-if="categories.length > 0" class="tag-cloud-card">
      <div class="tag-cloud-header">
        <span class="tag-cloud-title">📌 研究主题</span>
        <span class="tag-cloud-hint">点击筛选</span>
      </div>
      <div class="tag-cloud">
        <span
          v-for="cat in categories"
          :key="cat.name"
          class="cloud-tag"
          :class="{ 'cloud-tag-active': filterCategory === cat.name }"
          :style="{ fontSize: calcCloudSize(cat.count) }"
          @click="filterCategory = filterCategory === cat.name ? '' : cat.name"
        >
          {{ cat.name }}
          <small>({{ cat.count }})</small>
        </span>
      </div>
    </el-card>

    <!-- ===== 统计 + 操作栏 ===== -->
    <el-card class="stats-card">
      <div class="stats-grid">
        <div
          class="stat-item stat-total"
          :class="{ 'stat-active': filterCategory === '' }"
          @click="filterCategory = ''"
        >
          <div class="stat-icon">📊</div>
          <div class="stat-number">{{ statsData.total }}</div>
          <div class="stat-label">全部</div>
        </div>
        <div
          v-for="(count, cat) in catStats"
          :key="cat"
          class="stat-item"
          :class="{ 'stat-active': filterCategory === cat }"
          @click="filterCategory = filterCategory === cat ? '' : cat"
        >
          <div class="stat-number">{{ count }}</div>
          <div class="stat-label" :title="cat">{{ cat.length > 8 ? cat.slice(0, 8) + '…' : cat }}</div>
        </div>
      </div>
    </el-card>

    <!-- ===== 操作栏 ===== -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-input
            v-model="searchQuery"
            placeholder="搜索知识库..."
            clearable
            @keyup.enter="fetchKnowledge"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="12" :md="16">
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon> 添加知识
          </el-button>
          <el-button @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon> 上传文件
          </el-button>
          <el-button type="warning" @click="openQADialog">
            <el-icon><MagicStick /></el-icon> AI问答
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- ===== 知识列表 ===== -->
    <el-card class="knowledge-list-card">
      <div v-if="loading" class="skeleton-list">
        <div v-for="n in 4" :key="n" class="skeleton-item">
          <div class="skeleton-line skeleton-line-short"></div>
          <div class="skeleton-line skeleton-line-medium"></div>
          <div class="skeleton-line skeleton-line-long"></div>
        </div>
      </div>

      <div v-else-if="knowledgeList.length === 0" class="empty-state">
        <el-empty :description="searchQuery ? `没有找到「${searchQuery}」相关内容` : '暂无知识条目'" />
      </div>

      <div v-else class="knowledge-list">
        <div
          v-for="item in knowledgeList"
          :key="item.id"
          class="knowledge-item"
          @click="viewKnowledge(item)"
        >
          <div class="item-header">
            <div class="item-category">
              <span class="category-badge">{{ item.category || '未分类' }}</span>
              <el-tag
                v-if="item.analysis_status === 'pending'"
                size="small"
                type="warning"
                effect="light"
              >
                <span class="status-dot status-pending"></span> 分析中
              </el-tag>
              <el-tag
                v-if="item.analysis_status === 'analyzing'"
                size="small"
                type="warning"
                effect="light"
              >
                <span class="status-dot status-analyzing"></span> 分析中
              </el-tag>
              <el-tag
                v-if="item.analysis_status === 'failed'"
                size="small"
                type="danger"
                effect="light"
              >
                <span class="status-dot status-failed"></span> 失败
              </el-tag>
            </div>
            <div class="item-tags">
              <span
                v-for="tag in (item.tags || []).slice(0, 4)"
                :key="tag"
                class="tag-chip"
              >{{ tag }}</span>
              <span v-if="(item.tags || []).length > 4" class="tag-chip tag-more">
                +{{ item.tags.length - 4 }}
              </span>
            </div>
          </div>

          <h3 class="item-title">
            <el-icon v-if="item.file_path" style="margin-right: 4px; color: #409eff"><Document /></el-icon>
            <span v-if="item.source_type === 'conversation'" class="conversation-badge" title="来自对话记录">💬</span>
            <span v-if="item.source_type === 'auto_research'" class="auto-research-badge" title="AI自动研究">🤖</span>
            <span v-if="item.auto_researched" class="auto-researched-dot" title="已触发自主研究">🔄</span>
            {{ item.title }}
          </h3>
          <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
          <p v-else class="item-content">{{ item.content.substring(0, 150) }}...</p>

          <div class="item-footer">
            <div class="item-footer-left">
              <span v-if="item.knowledge_type" class="type-badge">{{ item.knowledge_type }}</span>
              <span class="item-time">{{ formatDate(item.created_at) }}</span>
            </div>
            <div class="item-actions">
              <el-button text type="primary" size="small" @click.stop="editKnowledge(item)">编辑</el-button>
              <el-button text type="danger" size="small" @click.stop="deleteKnowledge(item)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchKnowledge"
        />
      </div>
    </el-card>

    <!-- ===== 添加/编辑知识对话框 ===== -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingKnowledge ? '编辑知识' : '添加知识'"
      :width="isMobile ? '90vw' : '600px'"
      top="8vh"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="knowledgeForm" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="knowledgeForm.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="knowledgeForm.category" placeholder="动态分类" filterable allow-create clearable>
            <el-option
              v-for="cat in categories"
              :key="cat.name"
              :label="`${cat.name} (${cat.count})`"
              :value="cat.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="knowledgeForm.tags"
            multiple
            filterable
            allow-create
            placeholder="输入标签"
          >
            <el-option
              v-for="tag in hotTags"
              :key="tag.name"
              :label="`${tag.name} (${tag.count})`"
              :value="tag.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input
            v-model="knowledgeForm.content"
            type="textarea"
            :rows="8"
            placeholder="请输入知识内容"
          />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="knowledgeForm.source" placeholder="来源链接或文件路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveKnowledge">{{ editingKnowledge ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- ===== AI问答对话框 (RAG) ===== -->
    <el-dialog
      v-model="showQADialog"
      title="🤖 AI知识问答"
      :width="isMobile ? '92vw' : '700px'"
      top="5vh"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="qa-dialog">
        <div class="qa-input-row">
          <el-input
            v-model="qaQuery"
            placeholder="输入你的问题，AI会从知识库中查找并合成答案..."
            size="large"
            :disabled="qaLoading"
            @keyup.enter="handleQA"
          >
            <template #append>
              <el-button :loading="qaLoading" @click="handleQA">
                {{ qaLoading ? '思考中...' : '提问' }}
              </el-button>
            </template>
          </el-input>
        </div>

        <div class="qa-mode-toggle">
          <el-switch v-model="qaReasonMode" active-text="推理模式" inactive-text="检索模式" size="small" />
        </div>

        <!-- 快捷问题 -->
        <div v-if="!qaResult && !qaLoading" class="qa-suggestions">
          <div class="suggestion-title">💡 试试这些问题</div>
          <div class="suggestion-list">
            <el-tag
              v-for="q in suggestions"
              :key="q"
              class="suggestion-tag"
              @click="askSuggestion(q)"
            >{{ q }}</el-tag>
          </div>
        </div>

        <!-- 回答区域 -->
        <div v-if="qaLoading" class="qa-loading">
          <div class="qa-loading-dots">
            <span v-if="qaReasonMode">🧠</span>
            <span v-else>🔍</span>
            {{ qaReasonMode ? '正在遍历知识图谱推理链...' : '正在检索知识库...' }}
          </div>
        </div>

        <div v-if="qaResult" class="qa-result">
          <!-- 置信度 -->
          <div class="qa-confidence">
            <span class="confidence-dot" :class="'conf-' + qaResult.confidence"></span>
            {{ confidenceLabel(qaResult.confidence) }}
            <span class="confidence-info">基于 {{ qaResult.search_results?.high || 0 }} 条高相关、{{ qaResult.search_results?.total || 0 }} 条总检索结果</span>
          </div>

          <!-- 答案正文 -->
          <div class="qa-answer" v-html="renderAnswer(qaResult.answer)"></div>

          <!-- 来源引用 -->
          <div v-if="qaResult.sources && qaResult.sources.length" class="qa-sources">
            <div class="sources-title">📚 参考来源</div>
            <div
              v-for="src in qaResult.sources"
              :key="src.id"
              class="source-item"
              @click="gotoKnowledge(src.id)"
            >
              <span class="source-title">{{ src.title }}</span>
              <el-tag size="small" :type="src.relevance >= 0.7 ? 'success' : 'warning'">
                {{ (src.relevance * 100).toFixed(0) }}%
              </el-tag>
            </div>
          </div>

          <!-- 研究触发提示 -->
          <div v-if="qaResult.research_triggered && qaResult.research_queries?.length" class="qa-research-note">
            <el-alert
              title="知识库信息不足，已生成研究查询"
              :description="qaResult.research_queries.join('；')"
              type="warning"
              show-icon
              :closable="false"
            />
          </div>
        </div>

        <!-- 推理链（推理模式） -->
        <div v-if="qaReasonResult" class="qa-result">
          <div class="qa-confidence">
            <span class="confidence-dot" :class="'conf-' + qaReasonResult.confidence"></span>
            {{ confidenceLabel(qaReasonResult.confidence) }}
            <span class="confidence-info">推理链使用 {{ qaReasonResult.nodes_used }} 个节点，{{ qaReasonResult.hops_used }} 跳</span>
          </div>
          <div class="qa-answer" v-html="renderAnswer(qaReasonResult.answer)"></div>
          <div v-if="qaReasonResult.reasoning_chain?.length" class="qa-reasoning-chain">
            <div class="reasoning-title">🧠 推理路径</div>
            <div v-for="(step, i) in qaReasonResult.reasoning_chain" :key="i" class="reasoning-step">
              <span class="step-number">{{ i + 1 }}</span>
              <span>{{ step }}</span>
            </div>
          </div>
          <div v-if="qaReasonResult.gap_description" class="qa-gap-note">
            <el-alert :title="'推理缺口: ' + qaReasonResult.gap_description" type="warning" show-icon :closable="false" />
          </div>
        </div>

        <!-- 错误 -->
        <div v-if="qaError" class="qa-error">
          <el-alert :title="qaError" type="error" show-icon :closable="false" />
        </div>
      </div>
    </el-dialog>

    <!-- ===== 知识详情对话框（含关联 + 图谱） ===== -->
    <el-dialog
      v-model="showDetailDialog"
      title="知识详情"
      :width="isMobile ? '92vw' : '720px'"
      top="5vh"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-if="currentKnowledge" class="knowledge-detail">
        <h2>{{ currentKnowledge.title }}</h2>

        <div class="detail-meta">
          <span class="category-badge">{{ currentKnowledge.category || '未分类' }}</span>
          <span v-if="currentKnowledge.knowledge_type" class="type-badge">{{ currentKnowledge.knowledge_type }}</span>
          <span class="detail-date">{{ formatDate(currentKnowledge.created_at) }}</span>
          <el-tag
            v-if="currentKnowledge.analysis_status === 'pending' || currentKnowledge.analysis_status === 'analyzing'"
            size="small"
            type="warning"
          >分析中</el-tag>
          <el-tag
            v-if="currentKnowledge.analysis_status === 'failed'"
            size="small"
            type="danger"
          >分析失败</el-tag>
          <el-button
            v-if="currentKnowledge.analysis_status === 'failed'"
            size="small"
            type="danger"
            plain
            :loading="reanalyzing"
            @click="handleReanalyze(currentKnowledge.id)"
          >重新分析</el-button>
          <el-tag
            v-if="currentKnowledge.auto_researched"
            size="small"
            type="success"
          >自主研究</el-tag>
        </div>

        <div v-if="currentKnowledge.tags && currentKnowledge.tags.length" class="detail-tags">
          <span v-for="tag in currentKnowledge.tags" :key="tag" class="tag-chip detail-tag">{{ tag }}</span>
        </div>

        <!-- AI 分析信息 -->
        <div v-if="currentKnowledge.needs_review" class="detail-review-warning">
          <span>⚠️ 该条目与其他知识存在矛盾，待人工审阅</span>
          <el-button size="small" type="danger" plain @click="markReviewed(currentKnowledge.id)">标记已审阅</el-button>
        </div>

        <div v-if="currentKnowledge.key_concepts?.length || currentKnowledge.related_topics?.length" class="detail-analysis">
          <div v-if="currentKnowledge.key_concepts?.length" class="analysis-section">
            <span class="analysis-label">🔑 核心概念</span>
            <div class="analysis-items">
              <span v-for="c in currentKnowledge.key_concepts" :key="c" class="concept-chip">{{ c }}</span>
            </div>
          </div>
          <div v-if="currentKnowledge.related_topics?.length" class="analysis-section">
            <span class="analysis-label">🔗 关联主题</span>
            <div class="analysis-items">
              <span v-for="t in currentKnowledge.related_topics" :key="t" class="topic-chip">{{ t }}</span>
            </div>
          </div>
        </div>

        <!-- 知识三元组 -->
        <div v-if="currentKnowledge.entities?.length" class="detail-entities">
          <div class="entities-label">🧩 知识三元组</div>
          <div class="entities-grid">
            <div v-for="(e, i) in currentKnowledge.entities" :key="i" class="entity-card">
              <div class="entity-triple">
                <span class="entity-subject">{{ e.subject }}</span>
                <span class="entity-predicate">→ {{ e.predicate }} →</span>
                <span class="entity-object">{{ e.object }}</span>
              </div>
              <div v-if="e.condition" class="entity-condition">条件: {{ e.condition }}</div>
              <div class="entity-confidence">
                <el-progress :percentage="(e.confidence * 100).toFixed(0)" :stroke-width="4" :show-text="false" />
                <span class="confidence-text">{{ (e.confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 摘要 -->
        <div v-if="currentKnowledge.summary" class="detail-summary">
          <div class="summary-label">AI 摘要</div>
          <div class="summary-text">{{ currentKnowledge.summary }}</div>
        </div>

        <!-- 正文 -->
        <div class="detail-content-section">
          <div class="detail-content-header">
            <span class="section-label">正文</span>
            <el-button
              size="small"
              type="primary"
              plain
              :loading="reformatting"
              @click="handleReformat(currentKnowledge.id)"
            >
              {{ reformatting ? '排版中...' : 'AI 排版' }}
            </el-button>
          </div>
          <div
            v-if="currentKnowledge.formatted_content"
            class="detail-content markdown-body"
            v-html="renderMarkdown(currentKnowledge.formatted_content)"
          ></div>
          <div v-else class="detail-content">
            {{ currentKnowledge.content }}
          </div>
        </div>

        <!-- 来源 -->
        <div v-if="currentKnowledge.source || currentKnowledge.file_name || currentKnowledge.source_type" class="detail-source">
          <div v-if="currentKnowledge.source_type === 'conversation'" class="detail-conversation-source">
            <span>💬</span> 来自对话记录，AI 自动提取
          </div>
          <div v-if="currentKnowledge.source_type === 'auto_research'" class="detail-auto-source">
            <span>🤖</span> AI 自主研究入库
          </div>
          <div v-if="currentKnowledge.source">来源：{{ currentKnowledge.source }}</div>
          <div v-if="currentKnowledge.file_name">文件：{{ currentKnowledge.file_name }}</div>
        </div>

        <!-- ===== 相关知识 ===== -->
        <div v-if="relatedKnowledge.length > 0" class="detail-related">
          <div class="related-title">🔗 相关知识</div>
          <div
            v-for="rel in relatedKnowledge"
            :key="rel.id"
            class="related-item"
            @click="gotoKnowledge(rel.id)"
          >
            <div class="related-header">
              <span class="related-item-title">{{ rel.title }}</span>
              <el-tag size="small" :type="relationTagType(rel.relation_type)">
                {{ rel.relation_type }} {{ (rel.score * 100).toFixed(0) }}%
              </el-tag>
            </div>
            <div v-if="rel.reason" class="related-reason">{{ rel.reason }}</div>
          </div>
        </div>

        <!-- ===== 知识图谱 ===== -->
        <div class="detail-graph">
          <div class="graph-title">📊 知识图谱</div>
          <div v-if="graphData.nodes && graphData.nodes.length > 0">
            <div ref="graphRef" class="graph-container"></div>
          </div>
          <div v-else class="graph-empty">
            <el-icon :size="24" color="#c0c4cc"><Connection /></el-icon>
            <p>暂无关联数据</p>
            <p class="graph-empty-hint">后台分析完成后将自动生成知识关联图谱</p>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ===== 文件上传对话框 ===== -->
    <el-dialog v-model="showUploadDialog" title="上传文件到知识库" :width="isMobile ? '90vw' : '500px'" top="10vh" destroy-on-close>
      <div class="upload-ai-notice">
        <el-icon size="16" color="#409eff"><MagicStick /></el-icon>
        <span>上传后 AI 将自动分析内容，生成摘要、分类、标签和知识关联</span>
      </div>
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="uploadTitle" placeholder="留空则使用文件名" />
        </el-form-item>
      </el-form>
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.xlsx,.txt,.md"
        :on-change="onUploadFileChange"
        :on-exceed="() => ElMessage.warning('只能上传一个文件')"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF、Word(.docx)、Excel(.xlsx)、TXT、Markdown，最大 50MB</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          {{ uploading ? '分析中...' : '上传' }}
        </el-button>
      </template>
    </el-dialog>
      </el-tab-pane>

      <!-- ===== 实体图谱 Tab ===== -->
      <el-tab-pane label="实体图谱" name="entities">
        <el-card class="filter-card">
          <el-row :gutter="12">
            <el-col :span="5">
              <el-input v-model="entitySearch.subject" placeholder="主体" clearable @keyup.enter="searchEntities" />
            </el-col>
            <el-col :span="5">
              <el-input v-model="entitySearch.predicate" placeholder="关系" clearable @keyup.enter="searchEntities" />
            </el-col>
            <el-col :span="6">
              <el-input v-model="entitySearch.keyword" placeholder="关键字搜索" clearable @keyup.enter="searchEntities" />
            </el-col>
            <el-col :span="4">
              <el-button type="primary" @click="searchEntities">搜索实体</el-button>
            </el-col>
            <el-col :span="4">
              <el-button @click="fetchEntityGraph">图谱视图</el-button>
            </el-col>
          </el-row>
        </el-card>

        <el-card v-if="entityGraphData.nodes.length > 0" class="entity-graph-card">
          <div ref="entityGraphRef" class="entity-graph-container"></div>
        </el-card>

        <el-card class="entity-list-card">
          <div v-if="entityList.length === 0" class="empty-state">
            <el-empty description="暂无实体数据。上传文档后系统将自动提取知识三元组并跨文档合并。" />
          </div>
          <div v-else class="entity-grid">
            <div v-for="e in entityList" :key="e.id" class="entity-card clickable" @click="showEntityDetail(e.id)">
              <div class="entity-triple">
                <span class="entity-subject">{{ e.subject }}</span>
                <span class="entity-predicate">→ {{ e.predicate }} →</span>
                <span class="entity-object">{{ e.object }}</span>
              </div>
              <div v-if="e.condition" class="entity-condition-text">条件: {{ e.condition }}</div>
              <div class="entity-meta">
                <span>{{ e.source_count }} 篇文档</span>
                <span>{{ e.occurrence_count }} 次出现</span>
                <el-progress :percentage="Math.round(e.confidence * 100)" :stroke-width="4" :show-text="false" style="width:80px" />
              </div>
            </div>
          </div>
          <el-pagination v-if="entityTotal > 0" v-model:current-page="entityPage" :page-size="20"
            :total="entityTotal" layout="total, prev, pager, next" @current-change="searchEntities" style="margin-top:12px" />
        </el-card>
      </el-tab-pane>

      <!-- ===== 假设 Tab ===== -->
      <el-tab-pane label="科研假设" name="hypotheses">
        <el-card class="filter-card">
          <el-row :gutter="12" align="middle">
            <el-col :span="4">
              <el-select v-model="hypothesisFilter.status" placeholder="状态" clearable @change="fetchHypotheses">
                <el-option label="已提出" value="proposed" />
                <el-option label="已验证" value="validated" />
                <el-option label="已否决" value="rejected" />
              </el-select>
            </el-col>
            <el-col :span="4">
              <el-select v-model="hypothesisFilter.priority" placeholder="优先级" clearable @change="fetchHypotheses">
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-input v-model="hypothesisTopic" placeholder="研究领域（留空=全局）" clearable />
            </el-col>
            <el-col :span="5">
              <el-button type="primary" :loading="hypothesisGenerating" @click="generateHypotheses">
                <el-icon><MagicStick /></el-icon> 生成假设
              </el-button>
            </el-col>
          </el-row>
        </el-card>

        <div v-if="hypothesisGenerating" class="qa-loading">🔬 正在分析实体关系并生成假设...</div>

        <div v-else class="hypothesis-grid">
          <div v-for="h in hypothesisList" :key="h.id" class="hypothesis-card" :class="'hypothesis-' + h.status">
            <div class="hypothesis-header">
              <el-tag :type="hypothesisStatusTag(h.status)" size="small">{{ hypothesisStatusLabel(h.status) }}</el-tag>
              <el-tag :type="h.priority === 'high' ? 'danger' : h.priority === 'medium' ? 'warning' : 'info'" size="small" effect="plain">
                {{ h.priority === 'high' ? '高优先' : h.priority === 'medium' ? '中优先' : '低优先' }}
              </el-tag>
              <span class="hypothesis-confidence">{{ Math.round(h.confidence * 100) }}%</span>
            </div>
            <div class="hypothesis-statement">{{ h.statement }}</div>
            <div v-if="h.rationale" class="hypothesis-rationale"><strong>推导依据:</strong> {{ h.rationale }}</div>
            <div v-if="h.suggested_experiment" class="hypothesis-experiment"><strong>实验建议:</strong> {{ h.suggested_experiment }}</div>
            <div class="hypothesis-actions" v-if="h.status === 'proposed'">
              <el-button size="small" type="success" @click="validateHypothesis(h.id, 'validated')">验证通过</el-button>
              <el-button size="small" type="danger" @click="validateHypothesis(h.id, 'rejected')">否决</el-button>
            </div>
          </div>
        </div>
        <el-pagination v-if="hypothesisTotal > 0" v-model:current-page="hypothesisPage" :page-size="20"
          :total="hypothesisTotal" layout="total, prev, pager, next" @current-change="fetchHypotheses" style="margin-top:12px" />
      </el-tab-pane>

      <!-- ===== 公式计算 Tab ===== -->
      <el-tab-pane label="公式计算" name="formulas">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card class="formula-list-card">
              <div class="formula-list-header">
                <div class="formula-filter-row">
                  <el-tree-select
                    v-model="formulaCategoryFilter"
                    :data="formulaCategories"
                    :props="{ label: 'display_name', value: 'id', children: 'children' }"
                    placeholder="全部分类"
                    clearable
                    filterable
                    style="width:160px"
                    @change="fetchFormulas"
                  />
                  <el-select v-model="formulaSourceFilter" placeholder="来源" clearable @change="fetchFormulas" style="width:100px">
                    <el-option label="内置公式" value="builtin" />
                    <el-option label="文档提取" value="extracted" />
                  </el-select>
                  <el-input v-model="formulaKeyword" placeholder="搜索公式" clearable @keyup.enter="fetchFormulas" style="width:150px" />
                </div>
              </div>
              <div v-if="formulaList.length === 0" class="empty-state">
                <el-empty description="暂无公式。上传含数学公式的文档后系统将自动提取。" />
              </div>
              <div v-for="f in formulaList" :key="f.id" class="formula-item"
                :class="{ 'formula-selected': selectedFormula?.id === f.id }" @click="selectFormula(f)">
                <div class="formula-name">{{ f.name }}</div>
                <div class="formula-latex">{{ f.formula_latex }}</div>
                <div class="formula-meta">
                  <el-tag size="small">{{ f.domain || '未分类' }}</el-tag>
                  <el-tag v-if="f.source_type === 'builtin'" size="small" type="success" style="margin-left:4px">内置</el-tag>
                  <el-tag v-else-if="f.source_type === 'extracted'" size="small" type="info" style="margin-left:4px">提取</el-tag>
                  <span class="formula-unit">→ {{ f.result_unit }}</span>
                </div>
                <div v-if="f.category_name" class="formula-category-path">{{ f.category_name }}</div>
              </div>
              <el-pagination v-if="formulaTotal > 20" v-model:current-page="formulaPage" :page-size="20"
                :total="formulaTotal" layout="prev, pager, next" small @current-change="fetchFormulas" />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card v-if="selectedFormula" class="calculator-card">
              <h3>{{ selectedFormula.name }}</h3>
              <div v-if="selectedFormula.category_name" class="calc-category-path">分类: {{ selectedFormula.category_name }}</div>
              <div class="formula-meta" style="margin-top:4px">
                <el-tag v-if="selectedFormula.source_type === 'builtin'" size="small" type="success">内置公式</el-tag>
                <el-tag v-else-if="selectedFormula.source_type === 'extracted'" size="small" type="info">文档提取</el-tag>
              </div>
              <div class="calculator-formula">{{ selectedFormula.formula_latex }}</div>
              <el-divider />
              <el-form label-width="150px">
                <el-form-item v-for="(meta, varName) in selectedFormula.variables" :key="varName"
                  :label="`${meta.description || varName} (${meta.unit || ''})`">
                  <el-input-number v-model="calcInputs[varName]" :step="0.1" :precision="4" style="width:180px" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="calcLoading" @click="runCalculation">计算</el-button>
                </el-form-item>
              </el-form>
              <div v-if="calcResult" class="calc-result">
                <div class="calc-value">
                  结果: <strong>{{ calcResult.value }}</strong> <span class="calc-unit">{{ calcResult.unit }}</span>
                </div>
                <div v-if="calcResult.steps" class="calc-steps">
                  <div class="steps-title">计算步骤</div>
                  <div v-for="(step, i) in calcResult.steps" :key="i" class="calc-step">
                    <span class="step-var">{{ step.variable }}</span> = {{ step.value }} {{ step.unit }}
                  </div>
                </div>
                <div v-if="selectedFormula.knowledge_id" class="calc-source">来源: <a @click="gotoKnowledge(selectedFormula.knowledge_id)">知识条目 #{{ selectedFormula.knowledge_id }}</a></div>
              </div>
            </el-card>
            <el-card v-else class="calculator-card">
              <el-empty description="请从左侧选择一个公式" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

    </el-tabs>

    <!-- Entity detail dialog -->
    <el-dialog v-model="showEntityDetailDialog" title="实体详情" width="600px">
      <div v-if="entityDetail">
        <div class="entity-triple-large">
          <span class="entity-subject">{{ entityDetail.subject }}</span>
          <span class="entity-predicate">→ {{ entityDetail.predicate }} →</span>
          <span class="entity-object">{{ entityDetail.object }}</span>
        </div>
        <div v-if="entityDetail.condition" class="entity-condition-text">条件: {{ entityDetail.condition }}</div>
        <el-divider />
        <div class="entity-detail-section">
          <h4>来源文档 ({{ entityDetail.sources?.length || 0 }})</h4>
          <div v-for="src in entityDetail.sources" :key="src.id" class="source-item clickable" @click="gotoKnowledge(src.id); showEntityDetailDialog = false">
            {{ src.title }}
            <el-tag size="small">{{ src.category }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, watchEffect, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, MagicStick, Upload, Document, Connection } from '@element-plus/icons-vue'
import axios from 'axios'
import { formatDate } from '@/utils/format'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const isMobile = ref(window.innerWidth <= 768)
const knowledgeList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const filterCategory = ref('')
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showQADialog = ref(false)
const showUploadDialog = ref(false)
const editingKnowledge = ref(null)
const currentKnowledge = ref(null)
const loading = ref(false)
const reanalyzing = ref(false)
const reformatting = ref(false)
const statsData = ref({ total: 0, categories: {} })
const categories = ref([])
const hotTags = ref([])
const uploadTitle = ref('')
const uploadFile = ref(null)
const uploading = ref(false)
const uploadRef = ref(null)

// Tabs
const activeTab = ref('knowledge')

// Entity tab
const entitySearch = ref({ subject: '', predicate: '', keyword: '' })
const entityList = ref([])
const entityTotal = ref(0)
const entityPage = ref(1)
const entityGraphData = ref({ nodes: [], edges: [] })
const entityGraphRef = ref(null)
let entityChartInstance = null
const showEntityDetailDialog = ref(false)
const entityDetail = ref(null)

// Hypothesis tab
const hypothesisList = ref([])
const hypothesisTotal = ref(0)
const hypothesisPage = ref(1)
const hypothesisFilter = ref({ status: '', priority: '' })
const hypothesisTopic = ref('')
const hypothesisGenerating = ref(false)

// Formula tab
const formulaList = ref([])
const formulaTotal = ref(0)
const formulaPage = ref(1)
const formulaCategoryFilter = ref(null)
const formulaKeyword = ref('')
const formulaSourceFilter = ref('')
const formulaDomains = ref([])
const formulaCategories = ref([])
const selectedFormula = ref(null)
const calcInputs = ref({})
const calcResult = ref(null)
const calcLoading = ref(false)

// QA
const qaQuery = ref('')
const qaLoading = ref(false)
const qaResult = ref(null)
const qaError = ref('')
const suggestions = [
  '微纳米气泡在水处理中的应用',
  '臭氧微纳米气泡消毒效果',
  'NTA 粒径测量方法',
  '微纳米气泡在农业中的应用',
  '气泡稳定性影响因素',
]

// Detail extras
const relatedKnowledge = ref([])
const graphData = ref({ nodes: [], edges: [] })
const graphRef = ref(null)
let chartInstance = null

const knowledgeForm = ref({
  title: '',
  category: '',
  tags: [],
  content: '',
  source: ''
})

// 计算精简后的分类统计（只显示有数据的）
const catStats = computed(() => {
  return statsData.value.categories || {}
})

// ── 知识列表 ──

const fetchKnowledge = async () => {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchQuery.value) params.keyword = searchQuery.value
    if (filterCategory.value) params.category = filterCategory.value

    const res = await axios.get('/api/v1/knowledge', { params })
    knowledgeList.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取知识失败:', e)
  } finally {
    loading.value = false
  }
}

// ── 动态分类 + 标签 ──

const fetchCategories = async () => {
  try {
    const [catRes, tagRes] = await Promise.all([
      axios.get('/api/v1/knowledge/categories'),
      axios.get('/api/v1/knowledge/tags', { params: { min_freq: 1, limit: 30 } }),
    ])
    categories.value = catRes.data || []
    hotTags.value = tagRes.data || []
  } catch (e) {
    console.error('获取分类/标签失败:', e)
  }
}

// ── 统计 ──

const fetchStats = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/stats')
    statsData.value = res.data
  } catch (e) {
    console.error('获取统计失败:', e)
  }
}

// ── 保存/编辑/删除 ──

const saveKnowledge = async () => {
  if (!knowledgeForm.value.title || !knowledgeForm.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  try {
    if (editingKnowledge.value) {
      await axios.put(`/api/v1/knowledge/${editingKnowledge.value.id}`, knowledgeForm.value)
      ElMessage.success('知识更新成功')
    } else {
      await axios.post('/api/v1/knowledge', knowledgeForm.value)
      ElMessage.success('知识添加成功')
    }
    showCreateDialog.value = false
    editingKnowledge.value = null
    resetForm()
    fetchKnowledge()
    fetchStats()
    fetchCategories()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const editKnowledge = (item) => {
  editingKnowledge.value = item
  knowledgeForm.value = { ...item }
  showCreateDialog.value = true
}

const deleteKnowledge = async (item) => {
  try {
    await ElMessageBox.confirm('确定要删除这条知识吗？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/v1/knowledge/${item.id}`)
    ElMessage.success('知识删除成功')
    fetchKnowledge()
    fetchStats()
    fetchCategories()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleReanalyze = async (id) => {
  reanalyzing.value = true
  try {
    await axios.post(`/api/v1/knowledge/${id}/reanalyze`)
    ElMessage.success('已开始重新分析，请稍后查看结果')
    if (currentKnowledge.value) {
      currentKnowledge.value.analysis_status = 'analyzing'
    }
    fetchKnowledge()
  } catch (e) {
    ElMessage.error('重新分析触发失败')
  } finally {
    reanalyzing.value = false
  }
}

const renderMarkdown = (text) => {
  if (!text) return ''
  const raw = marked.parse(text)
  return DOMPurify.sanitize(raw)
}

const handleReformat = async (id) => {
  reformatting.value = true
  try {
    await axios.post(`/api/v1/knowledge/${id}/reformat`)
    ElMessage.success('AI 排版已开始，请稍后刷新查看')
    reformatting.value = false
    // 5秒后自动刷新
    setTimeout(async () => {
      try {
        const { data } = await axios.get(`/api/v1/knowledge/${id}`)
        currentKnowledge.value = { ...currentKnowledge.value, ...data }
        ElMessage.success('排版完成')
      } catch (e) { /* ignore */ }
      reformatting.value = false
    }, 5000)
  } catch (e) {
    ElMessage.error('排版触发失败')
    reformatting.value = false
  }
}

// ── 知识详情 + 关联 + 图谱 ──

const viewKnowledge = async (item) => {
  currentKnowledge.value = item
  showDetailDialog.value = true
  relatedKnowledge.value = []
  graphData.value = { nodes: [], edges: [] }
  window.scrollTo({ top: 0, behavior: 'smooth' })

  // 并行获取关联和图谱数据
  try {
    const [relRes, graphRes] = await Promise.all([
      axios.get(`/api/v1/knowledge/${item.id}/related`, { params: { limit: 8 } }),
      axios.get('/api/v1/knowledge/graph', { params: { center_id: item.id, depth: 1, limit: 30 } }),
    ])
    relatedKnowledge.value = relRes.data || []
    graphData.value = graphRes.data || { nodes: [], edges: [] }
  } catch (e) {
    console.error('获取关联数据失败:', e)
  }
}

// 渲染 ECharts 图谱 — 监听 graphData 变化，数据到达后自动渲染
watchEffect(async () => {
  const nodes = graphData.value.nodes
  if (nodes && nodes.length > 0 && showDetailDialog.value) {
    await nextTick()
    if (graphRef.value) {
      renderGraph()
    }
  }
})

// 关闭弹窗时清理图表实例
watch(showDetailDialog, (val) => {
  if (!val && chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const renderGraph = async () => {
  if (!graphRef.value) return
  const echarts = await import('echarts')
  if (chartInstance) chartInstance.dispose()

  chartInstance = echarts.init(graphRef.value)
  const data = graphData.value

  // 颜色映射
  const colorMap = {}
  const colors = ['#FF7A5C', '#FFB347', '#409eff', '#67c23a', '#e6a23c', '#909399', '#f56c6c']
  let colorIdx = 0

  data.nodes.forEach(n => {
    if (!colorMap[n.category]) {
      colorMap[n.category] = colors[colorIdx % colors.length]
      colorIdx++
    }
  })

  chartInstance.setOption({
    tooltip: {
      formatter: (p) => {
        if (p.dataType === 'node') {
          return `<b>${p.data.title}</b><br/>分类: ${p.data.category}<br/>关联: ${p.data.size.toFixed(0)}`
        }
        return `${p.data.type}: ${(p.data.score * 100).toFixed(0)}%`
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: data.nodes.map(n => ({
        id: n.id,
        name: n.title?.length > 12 ? n.title.slice(0, 12) + '…' : n.title,
        title: n.title,
        category: n.category,
        value: n.size,
        symbolSize: Math.max(20, Math.min(50, n.size * 8)),
        itemStyle: { color: colorMap[n.category] || '#909399' },
      })),
      edges: data.edges.map(e => ({
        source: e.source,
        target: e.target,
        type: e.type,
        score: e.score,
        lineStyle: {
          width: Math.max(1, e.score * 4),
          opacity: 0.6,
          curveness: 0.1,
          color: e.type === 'contradicts' ? '#f56c6c' : undefined,
          type: e.type === 'contradicts' ? 'dashed' : 'solid',
        },
        label: { show: e.score > 0.8, formatter: e.type, fontSize: 10 },
      })),
      force: { repulsion: 300, edgeLength: 120 },
      label: { show: true, fontSize: 10, color: '#333' },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 },
      },
    }],
  })
}

const gotoKnowledge = (id) => {
  // 根据ID重新获取详情
  axios.get(`/api/v1/knowledge/${id}`).then(res => {
    viewKnowledge(res.data)
  }).catch(() => {
    ElMessage.warning('该知识条目可能已被删除')
  })
}

// ── AI 问答 (RAG) ──

const openQADialog = () => {
  qaQuery.value = ''
  qaResult.value = null
  qaError.value = ''
  showQADialog.value = true
}

const askSuggestion = (q) => {
  qaQuery.value = q
  handleQA()
}

const confidenceLabel = (level) => {
  const map = { high: '高置信度', medium: '中等置信度', low: '低置信度' }
  return map[level] || level
}

const renderAnswer = (text) => {
  if (!text) return ''
  // HTML 转义（防 XSS），仅 [来源:xxx] 转为安全标签
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/\[来源:([^\]]+)\]/g, '<span class="qa-citation">📖 $1</span>')
}

// ── 文件上传 ──

const onUploadFileChange = (file) => {
  uploadFile.value = file.raw
}

const handleUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    if (uploadTitle.value) formData.append('title', uploadTitle.value)

    await axios.post('/api/v1/knowledge/upload', formData, { timeout: 180000 })
    ElMessage.success('文件上传成功，后台正在分析...')
    showUploadDialog.value = false
    uploadTitle.value = ''
    uploadFile.value = null
    if (uploadRef.value) uploadRef.value.clearFiles()
    fetchKnowledge()
    fetchStats()
  } catch (e) {
    if (e.code === 'ECONNABORTED') {
      ElMessage.error('上传超时，请检查网络或尝试更小的文件')
    } else if (!e.response) {
      ElMessage.error('网络连接失败，请检查网络后重试')
    } else {
      const detail = e.response?.data?.detail
      if (Array.isArray(detail)) {
        ElMessage.error(detail.map(d => d.msg || JSON.stringify(d)).join('; '))
      } else if (typeof detail === 'string') {
        ElMessage.error(detail)
      } else if (typeof e.response?.data === 'string') {
        // Nginx 返回的 HTML 错误页等非 JSON 响应
        ElMessage.error('服务器错误，请稍后重试')
      } else {
        ElMessage.error('上传失败')
      }
    }
  } finally {
    uploading.value = false
  }
}

// ── 工具函数 ──

const relationTagType = (type) => {
  const map = {
    similar: 'success',
    supplements: 'warning',
    extends: '',
    supports: '',
    contradicts: 'danger',
    method_inherits: 'primary',
    cites: 'info',
    prerequisite: 'warning',
    compares: 'primary',
  }
  return map[type] || 'info'
}

const markReviewed = async (id) => {
  try {
    await axios.post(`/api/v1/knowledge/${id}/review`)
    if (currentKnowledge.value) currentKnowledge.value.needs_review = false
    ElMessage.success('已标记为已审阅')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

// QA reasoning mode
const qaReasonMode = ref(false)
const qaReasonResult = ref(null)

const handleQA = async () => {
  const q = qaQuery.value.trim()
  if (!q) { ElMessage.warning('请输入问题'); return }
  qaLoading.value = true
  qaResult.value = null
  qaError.value = ''
  qaReasonResult.value = null
  try {
    if (qaReasonMode.value) {
      const { data } = await axios.post('/api/v1/knowledge/reason', { question: q, max_hops: 2, top_k: 6 })
      qaReasonResult.value = data
    } else {
      const { data } = await axios.post('/api/v1/knowledge/qa', { question: q, top_k: 8, auto_research: true })
      qaResult.value = data
    }
  } catch (e) {
    qaError.value = e.response?.data?.detail || '问答失败，请稍后重试'
  } finally {
    qaLoading.value = false
  }
}

const resetForm = () => {
  knowledgeForm.value = { title: '', category: '', tags: [], content: '', source: '' }
}

const calcCloudSize = (count) => {
  const maxCount = Math.max(...categories.value.map(c => c.count), 1)
  const ratio = Math.log2(1 + count) / Math.log2(1 + maxCount)
  return `${13 + ratio * 9}px`
}

watch(filterCategory, () => {
  currentPage.value = 1
  fetchKnowledge()
})

// 清空搜索时自动刷新
watch(searchQuery, (val) => {
  if (!val) {
    currentPage.value = 1
    fetchKnowledge()
  }
})

const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
}

onMounted(() => {
  fetchKnowledge()
  fetchStats()
  fetchCategories()
  window.addEventListener('resize', handleResize)
})

// ── Entity methods ──

const searchEntities = async () => {
  try {
    const params = { ...entitySearch.value, page: entityPage.value, page_size: 20 }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const res = await axios.get('/api/v1/knowledge/entities', { params })
    entityList.value = res.data.items || []
    entityTotal.value = res.data.total || 0
  } catch (e) { ElMessage.error('实体搜索失败') }
}

const fetchEntityGraph = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/entities/graph', { params: { limit: 80 } })
    entityGraphData.value = res.data
    await nextTick()
    renderEntityGraph()
  } catch (e) { console.error('实体图谱加载失败:', e) }
}

const renderEntityGraph = async () => {
  if (!entityGraphRef.value || entityGraphData.value.nodes.length === 0) return
  const echarts = await import('echarts')
  if (entityChartInstance) entityChartInstance.dispose()
  entityChartInstance = echarts.init(entityGraphRef.value)
  const cats = [...new Set(entityGraphData.value.nodes.map(n => n.predicate || '其他'))]
  const colors = ['#FF7A5C', '#FFB347', '#5470c6', '#91cc75', '#ee6666', '#73c0de', '#fc8452']
  const option = {
    tooltip: { formatter: p => p.dataType === 'node' ? `${p.data.subject}<br/>${p.data.predicate} → ${p.data.object}` : `共现权重: ${p.data.weight || 1}` },
    legend: { data: cats.slice(0, 7), bottom: 0 },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 200, edgeLength: [100, 300] },
      data: entityGraphData.value.nodes.map(n => ({
        name: String(n.id), subject: n.subject, predicate: n.predicate, object: n.object,
        symbolSize: Math.max(15, Math.min(40, (n.occurrence_count || 1) * 6)),
        category: n.predicate || '其他', itemStyle: { color: colors[cats.indexOf(n.predicate || '其他') % colors.length] },
      })),
      categories: cats.slice(0, 7).map((c, i) => ({ name: c, itemStyle: { color: colors[i % colors.length] } })),
      links: entityGraphData.value.edges.map(e => ({ source: String(e.source), target: String(e.target), weight: e.weight })),
      lineStyle: { opacity: 0.4, curveness: 0.2 },
      label: { show: true, formatter: p => p.data.subject.length > 8 ? p.data.subject.slice(0, 8) + '...' : p.data.subject, fontSize: 10 },
    }],
  }
  entityChartInstance.setOption(option)
}

const showEntityDetail = async (id) => {
  try {
    const res = await axios.get(`/api/v1/knowledge/entities/${id}`)
    entityDetail.value = res.data
    showEntityDetailDialog.value = true
  } catch (e) { ElMessage.error('获取实体详情失败') }
}

// ── Hypothesis methods ──

const fetchHypotheses = async () => {
  try {
    const params = { page: hypothesisPage.value, page_size: 20 }
    if (hypothesisFilter.value.status) params.status = hypothesisFilter.value.status
    if (hypothesisFilter.value.priority) params.priority = hypothesisFilter.value.priority
    const res = await axios.get('/api/v1/knowledge/hypotheses', { params })
    hypothesisList.value = res.data.items || []
    hypothesisTotal.value = res.data.total || 0
  } catch (e) { console.error('获取假设失败:', e) }
}

const generateHypotheses = async () => {
  hypothesisGenerating.value = true
  try {
    await axios.post('/api/v1/knowledge/hypotheses', {
      topic: hypothesisTopic.value || null,
      count: 3,
    })
    hypothesisGenerating.value = false
    await fetchHypotheses()
    ElMessage.success('假设生成完成')
  } catch (e) {
    hypothesisGenerating.value = false
    ElMessage.error('假设生成失败')
  }
}

const hypothesisStatusTag = (s) => s === 'validated' ? 'success' : s === 'rejected' ? 'danger' : 'warning'
const hypothesisStatusLabel = (s) => s === 'validated' ? '已验证' : s === 'rejected' ? '已否决' : '已提出'

const validateHypothesis = async (id, status) => {
  try {
    await axios.post(`/api/v1/knowledge/hypotheses/${id}/validate`, { status })
    ElMessage.success(status === 'validated' ? '已标记为验证通过' : '已否决')
    await fetchHypotheses()
  } catch (e) { ElMessage.error('操作失败') }
}

// ── Formula methods ──

const fetchFormulas = async () => {
  try {
    const params = { page: formulaPage.value, page_size: 20 }
    if (formulaCategoryFilter.value) params.category_id = formulaCategoryFilter.value
    if (formulaKeyword.value) params.keyword = formulaKeyword.value
    if (formulaSourceFilter.value) params.source_type = formulaSourceFilter.value
    const res = await axios.get('/api/v1/knowledge/formulas', { params })
    formulaList.value = res.data.items || []
    formulaTotal.value = res.data.total || 0
  } catch (e) { console.error('获取公式失败:', e) }
}

const fetchFormulaCategories = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/formulas/categories')
    formulaCategories.value = res.data || []
  } catch (e) { console.error('获取公式分类树失败:', e) }
}

const fetchFormulaDomains = async () => {
  try {
    const res = await axios.get('/api/v1/knowledge/formulas/domains')
    formulaDomains.value = res.data || []
  } catch (e) { console.error('获取公式领域失败:', e) }
}

const selectFormula = (f) => {
  selectedFormula.value = f
  calcInputs.value = {}
  calcResult.value = null
  if (f.variables) {
    for (const [k, meta] of Object.entries(f.variables)) {
      calcInputs.value[k] = meta.default ?? 0
    }
  }
}

const runCalculation = async () => {
  if (!selectedFormula.value) return
  calcLoading.value = true
  calcResult.value = null
  try {
    const res = await axios.post('/api/v1/knowledge/formulas/calculate', {
      formula_id: selectedFormula.value.id,
      variables: calcInputs.value,
    })
    calcResult.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '计算失败')
  } finally { calcLoading.value = false }
}

// ── Tab watcher ──

watch(activeTab, (tab) => {
  if (tab === 'entities') { searchEntities(); fetchEntityGraph() }
  if (tab === 'hypotheses') fetchHypotheses()
  if (tab === 'formulas') { fetchFormulas(); fetchFormulaCategories() }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

/* ── Tag Cloud ── */
.tag-cloud-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.tag-cloud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.tag-cloud-title {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.tag-cloud-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.cloud-tag {
  cursor: pointer;
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  background: var(--color-info-bg);
  color: var(--color-text-regular);
  transition: all var(--duration-normal) var(--ease-out);
  white-space: nowrap;
}

.cloud-tag:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  transform: scale(1.05);
}

.cloud-tag-active {
  background: var(--color-primary) !important;
  color: #fff !important;
}

.cloud-tag small {
  font-size: 11px;
  opacity: 0.7;
}

/* ── Stats ── */
.stats-card {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-primary);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 40ms both;
}

.stats-grid {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.stat-item {
  text-align: center;
  cursor: pointer;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-lg);
  transition: all var(--duration-normal) var(--ease-out);
  color: rgba(255, 255, 255, 0.85);
  min-width: 60px;
}

.stat-item:hover,
.stat-active {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.stat-icon {
  font-size: 22px;
  margin-bottom: var(--space-1);
}

.stat-number {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  line-height: 1.2;
}

.stat-label {
  font-size: var(--font-size-xs);
  margin-top: var(--space-1);
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── List ── */
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.knowledge-item {
  padding: var(--space-4);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.knowledge-item:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-2px);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}

.item-category {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.category-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.tag-chip {
  display: inline-block;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  font-size: 11px;
  background: var(--color-info-bg);
  color: var(--color-text-regular);
  margin-left: var(--space-1);
  transition: all var(--duration-fast) var(--ease-out);
}

.tag-chip:hover {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.tag-more {
  background: #e8f4fd;
  color: var(--color-primary);
}

.item-title {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
  display: flex;
  align-items: center;
}

.conversation-badge,
.auto-research-badge {
  display: inline-block;
  margin-right: var(--space-1);
  font-size: var(--font-size-sm);
  vertical-align: middle;
  opacity: 0.8;
}

.auto-researched-dot {
  margin-right: 2px;
  font-size: var(--font-size-sm);
}

.item-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-3);
  font-style: italic;
}

.item-content {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.6;
  margin-bottom: var(--space-3);
}

.item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.item-footer-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.type-badge {
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  font-size: 10px;
  background: #f0f5ff;
  color: #409eff;
  border: 1px solid #d6e4ff;
}

.item-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.item-actions {
  display: flex;
  gap: var(--space-2);
}

.item-actions .el-button {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.item-actions .el-button:hover {
  transform: scale(1.02);
}

.pagination {
  margin-top: var(--space-5);
  display: flex;
  justify-content: flex-end;
}

/* ── QA Dialog ── */
.qa-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.qa-input-row {
  display: flex;
  gap: var(--space-2);
}

.qa-mode-toggle {
  display: flex;
  justify-content: flex-end;
  padding: var(--space-2) 0;
}

.qa-reasoning-chain {
  margin-top: var(--space-4);
  padding: var(--space-3);
  background: #f5f7fa;
  border-radius: var(--radius-md);
}

.reasoning-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.reasoning-step {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.step-number {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  font-size: var(--font-size-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-semibold);
}

.qa-gap-note {
  margin-top: var(--space-3);
}

.qa-suggestions {
  padding: var(--space-3) 0;
}

.suggestion-title {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.suggestion-tag {
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.suggestion-tag:hover {
  transform: scale(1.04);
}

.qa-loading {
  text-align: center;
  padding: var(--space-8);
  color: var(--color-text-secondary);
}

.qa-loading-dots {
  font-size: var(--font-size-base);
  animation: pulse 1.5s ease-in-out infinite;
}

.qa-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.qa-confidence {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.confidence-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.conf-high { background: #67c23a; }
.conf-medium { background: #e6a23c; }
.conf-low { background: #f56c6c; }

.confidence-info {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-left: var(--space-2);
}

.qa-answer {
  background: var(--color-bg-page);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  line-height: 1.8;
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
}

.qa-citation {
  display: inline-block;
  padding: 0 var(--space-1);
  color: var(--color-primary);
  cursor: pointer;
  font-size: var(--font-size-sm);
}

.qa-sources {
  background: #f0f9f0;
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.sources-title {
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-3);
  color: var(--color-text-primary);
}

.source-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast);
}

.source-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.source-title {
  font-size: var(--font-size-sm);
  color: var(--color-primary);
}

.qa-research-note {
  margin-top: var(--space-2);
}

.qa-error {
  margin-top: var(--space-2);
}

/* ── Detail Dialog ── */
.knowledge-detail {
  max-height: 75vh;
  overflow-y: auto;
  padding-right: var(--space-2);
}

.knowledge-detail h2 {
  margin-bottom: var(--space-4);
  color: var(--color-text-primary);
  font-size: var(--font-size-xl);
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.detail-date {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.detail-tags {
  margin-bottom: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.detail-tag {
  font-size: var(--font-size-xs);
}

.detail-analysis {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.analysis-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.analysis-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.analysis-items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.concept-chip {
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: 11px;
  background: #f0f5ff;
  color: #409eff;
  border: 1px solid #d6e4ff;
}

.topic-chip {
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: 11px;
  background: #fef7e0;
  color: #b8860b;
  border: 1px solid #fce8b2;
}

/* Needs review warning */
.detail-review-warning {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  color: #f56c6c;
  font-weight: var(--font-weight-semibold);
}

/* Entity triples */
.detail-entities {
  margin-bottom: var(--space-4);
}

.entities-label {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-3);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.entities-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
}

.entity-card {
  background: #fafbfc;
  border: 1px solid #e8eaed;
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.entity-triple {
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-1);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.entity-subject {
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.entity-predicate {
  color: #909399;
}

.entity-object {
  color: #409eff;
  font-weight: var(--font-weight-medium);
}

.entity-condition {
  font-size: var(--font-size-xs);
  color: #909399;
  margin-bottom: var(--space-1);
}

.entity-confidence {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.entity-confidence .el-progress { flex: 1; }
.confidence-text { font-size: var(--font-size-xs); color: #909399; }

.detail-summary {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #e8f4fd 100%);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-5);
  border-left: 4px solid var(--color-primary);
}

.summary-label {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.summary-text {
  font-size: var(--font-size-base);
  line-height: 1.7;
  color: var(--color-text-primary);
}

.detail-content {
  font-size: var(--font-size-base);
  line-height: 1.8;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  background: var(--color-bg-page);
  padding: var(--space-4);
  border-radius: var(--radius-md);
}

.detail-content-section {
  margin-top: var(--space-4);
}

.detail-content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.section-label {
  font-weight: 600;
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
}

.markdown-body {
  font-size: var(--font-size-base);
  line-height: 1.8;
  color: var(--color-text-primary);
  background: var(--color-bg-page);
  padding: var(--space-4) var(--space-6);
  border-radius: var(--radius-md);
}

.markdown-body :deep(h1) {
  font-size: 1.5em;
  font-weight: 700;
  margin: 1.2em 0 0.6em;
  padding-bottom: 0.3em;
  border-bottom: 2px solid var(--color-border);
  color: var(--color-text-primary);
}

.markdown-body :deep(h2) {
  font-size: 1.3em;
  font-weight: 600;
  margin: 1em 0 0.5em;
  color: var(--color-text-primary);
}

.markdown-body :deep(h3) {
  font-size: 1.1em;
  font-weight: 600;
  margin: 0.8em 0 0.4em;
  color: var(--color-text-secondary);
}

.markdown-body :deep(p) {
  margin: 0.5em 0;
  text-indent: 2em;
}

.markdown-body :deep(ul), .markdown-body :deep(ol) {
  padding-left: 2em;
  margin: 0.4em 0;
}

.markdown-body :deep(li) {
  margin: 0.2em 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.8em 0;
  font-size: 0.9em;
}

.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--color-border);
  padding: 0.4em 0.6em;
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--color-bg-page);
  font-weight: 600;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  margin: 0.6em 0;
  padding: 0.3em 1em;
  color: var(--color-text-secondary);
  background: var(--color-bg-page);
}

.markdown-body :deep(code) {
  background: #f0f0f0;
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.9em;
}

.markdown-body :deep(sub) { font-size: 0.8em; }
.markdown-body :deep(sup) { font-size: 0.8em; }

.detail-source {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.detail-conversation-source,
.detail-auto-source {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}

/* ── Related Knowledge ── */
.detail-related {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.related-title {
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-3);
  color: var(--color-text-primary);
}

.related-item {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  margin-bottom: var(--space-2);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.related-item:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}

.related-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.related-item-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-primary);
}

.related-reason {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

/* ── Knowledge Graph ── */
.detail-graph {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.graph-title {
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-3);
  color: var(--color-text-primary);
}

.graph-container {
  width: 100%;
  min-height: 250px;
  max-height: 45vh;
  height: 350px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  background: var(--color-bg-page);
}

.graph-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 150px;
  color: var(--color-text-secondary);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-page);
}

.graph-empty p {
  margin: var(--space-1) 0;
  font-size: var(--font-size-sm);
}

.graph-empty-hint {
  font-size: var(--font-size-xs) !important;
  opacity: 0.7;
}

/* ── Upload ── */
.upload-ai-notice {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-primary-bg);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-primary);
}

/* ── Misc ── */
.filter-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

.knowledge-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 120ms both;
}

.empty-state {
  padding: var(--space-12) 0;
}

/* ── Skeleton Loading ── */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.skeleton-item {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
}

.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--color-border) 25%, #e8e8e8 50%, var(--color-border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  margin-bottom: var(--space-3);
}

.skeleton-line-short { width: 30%; }
.skeleton-line-medium { width: 60%; }
.skeleton-line-long { width: 90%; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Status Dots ── */
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}

.status-pending {
  background: #e6a23c;
  animation: pulse 1.5s ease-in-out infinite;
}

.status-analyzing {
  background: #e6a23c;
  animation: pulse 0.8s ease-in-out infinite;
}

.status-failed {
  background: #f56c6c;
}

/* ── Mobile Responsive ── */
@media (max-width: 768px) {
  .knowledge-view {
    gap: var(--space-3);
  }

  .stats-grid {
    gap: var(--space-2);
  }

  .stat-item {
    padding: var(--space-1) var(--space-2);
    min-width: 48px;
  }

  .stat-label {
    max-width: 60px;
    font-size: 10px;
  }

  .stat-number {
    font-size: var(--font-size-lg);
  }

  .cloud-tag {
    padding: 2px var(--space-2);
    font-size: 12px;
  }

  .knowledge-item {
    padding: var(--space-3);
  }

  .item-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .item-footer {
    flex-direction: column;
    gap: var(--space-2);
  }

  .item-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .graph-container {
    height: 250px;
  }

  .detail-content {
    font-size: var(--font-size-sm);
  }

  .filter-card .el-row {
    gap: var(--space-2);
  }

  .filter-card .el-col {
    margin-bottom: var(--space-2);
  }

  .qa-dialog {
    gap: var(--space-2);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── Entity detail ── */
.entity-triple-large {
  font-size: var(--font-size-lg); padding: var(--space-4);
  background: var(--color-primary-bg); border-radius: var(--radius-md);
  display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;
}
.entity-detail-section h4 { margin: 0 0 8px 0; }
.source-item.clickable {
  padding: var(--space-2); border-radius: var(--radius-sm);
  cursor: pointer; display: flex; align-items: center; justify-content: space-between;
}
.source-item.clickable:hover { background: var(--color-bg-page); }

/* ── Entity tab ── */
.entity-graph-container {
  width: 100%; height: 350px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  background: var(--color-bg-page);
}
.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-3);
}
.entity-card.clickable {
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  transition: all var(--duration-fast);
}
.entity-card.clickable:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
}
.entity-triple {
  display: flex; align-items: center; gap: var(--space-1);
  font-size: var(--font-size-sm);
  flex-wrap: wrap;
}
.entity-subject { color: var(--color-primary); font-weight: var(--font-weight-semibold); }
.entity-predicate { color: var(--color-text-secondary); font-size: 12px; }
.entity-object { color: var(--color-text-primary); }
.entity-condition-text { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.entity-meta {
  display: flex; align-items: center; gap: var(--space-2);
  margin-top: var(--space-2); font-size: 12px;
  color: var(--color-text-secondary);
}

/* ── Hypothesis tab ── */
.hypothesis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--space-4);
}
.hypothesis-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  transition: all var(--duration-fast);
}
.hypothesis-card:hover { box-shadow: var(--shadow-primary); }
.hypothesis-card.hypothesis-validated { border-left: 4px solid #67c23a; }
.hypothesis-card.hypothesis-rejected { border-left: 4px solid #f56c6c; opacity: 0.7; }
.hypothesis-header {
  display: flex; align-items: center; gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.hypothesis-confidence { font-size: 12px; color: var(--color-text-secondary); margin-left: auto; }
.hypothesis-statement {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  margin: var(--space-3) 0;
  line-height: 1.6;
}
.hypothesis-rationale, .hypothesis-experiment {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
  line-height: 1.5;
}
.hypothesis-actions { margin-top: var(--space-3); display: flex; gap: var(--space-2); }

/* ── Formula tab ── */
.formula-list-header {
  display: flex; gap: var(--space-2); margin-bottom: var(--space-3);
}
.formula-filter-row {
  display: flex; gap: var(--space-2); flex-wrap: wrap;
}
.formula-item {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  cursor: pointer;
  transition: all var(--duration-fast);
}
.formula-item:hover, .formula-item.formula-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}
.formula-name { font-weight: var(--font-weight-semibold); margin-bottom: 4px; }
.formula-latex { font-size: 13px; color: var(--color-text-secondary); font-family: monospace; margin-bottom: 4px; }
.formula-meta { display: flex; align-items: center; gap: var(--space-2); }
.formula-unit { font-size: 12px; color: var(--color-text-secondary); }
.formula-category-path { font-size: 11px; color: var(--color-text-placeholder); margin-top: 2px; }
.calc-category-path { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 4px; }
.calculator-card h3 { margin: 0 0 8px 0; }
.calculator-formula {
  font-size: 16px; font-family: monospace;
  padding: var(--space-3); background: var(--color-bg-page);
  border-radius: var(--radius-md);
}
.calc-result {
  margin-top: var(--space-4);
  padding: var(--space-3);
  background: var(--color-primary-bg);
  border-radius: var(--radius-md);
}
.calc-value { font-size: 18px; margin-bottom: 8px; }
.calc-value strong { color: var(--color-primary); font-size: 24px; }
.calc-unit { color: var(--color-text-secondary); font-size: 14px; }
.calc-steps { margin-top: var(--space-3); }
.steps-title { font-weight: var(--font-weight-semibold); margin-bottom: 8px; }
.calc-step { font-size: 13px; padding: 4px 0; border-bottom: 1px dashed var(--color-border); }
.step-var { font-weight: var(--font-weight-semibold); color: var(--color-primary); }
.calc-source { margin-top: var(--space-3); font-size: 12px; color: var(--color-text-secondary); }
.calc-source a { color: var(--color-primary); cursor: pointer; text-decoration: underline; }

/* ── Tabs ── */
.knowledge-tabs {
  background: transparent;
  box-shadow: none;
}
.knowledge-tabs :deep(.el-tabs__header) {
  background: var(--color-bg-card);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  margin-bottom: 0;
}
.knowledge-tabs :deep(.el-tabs__content) {
  padding: var(--space-4);
  background: var(--color-bg-card);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}
</style>
