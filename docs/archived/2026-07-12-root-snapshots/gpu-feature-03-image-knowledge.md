# GPU 功能 03: 图片知识库 — 详细实施计划

> 预计周期: **4-6 周** | 优先级: 🔴 高 | GPU 需求: ~3GB

## 功能概述

构建图片知识库，支持实验图片智能分析、以图搜图、图片自动分类标注、显微镜图片分析。

---

## 3.1 图片上传与存储

### 3.1.1 图片上传
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 批量上传 | 支持拖拽批量上传 | 2d |
| 格式支持 | PNG/JPG/BMP/TIFF/WebP | 1d |
| 图片压缩 | 自动压缩到合理大小 | 1d |
| 缩略图 | 自动生成缩略图 | 1d |
| EXIF 提取 | 提取图片元数据 | 1d |

**验收标准**: 支持批量上传多种格式图片

### 3.1.2 图片存储
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| MinIO 存储 | 原图+缩略图分开存储 | 1d |
| 数据库索引 | image_knowledge 表 | 1d |
| 图片分类 | 按实验/项目/类型分类 | 1d |
| 版本管理 | 图片版本管理 | 1d |

**验收标准**: 图片可分类存储和管理

---

## 3.2 图片智能分析

### 3.2.1 图片内容识别
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| CLIP 集成 | OpenAI CLIP 图片理解 | 2d |
| 图片分类 | 自动分类图片类型 | 2d |
| 场景识别 | 识别实验场景 | 2d |
| 物体检测 | 检测图片中的物体 | 2d |

**验收标准**: 自动识别图片内容和场景

### 3.2.2 显微镜图片分析
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 气泡检测 | 检测图片中的气泡 | 3d |
| 尺寸测量 | 测量气泡尺寸 | 3d |
| 分布统计 | 统计气泡尺寸分布 | 2d |
| 形态分析 | 分析气泡形态特征 | 2d |

```python
# 气泡检测算法
def detect_bubbles(image):
    # 1. 图像预处理
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 2. 阈值分割
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 3. 轮廓检测
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 4. 筛选气泡
    bubbles = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 50 < area < 10000:  # 面积筛选
            perimeter = cv2.arcLength(contour, True)
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity > 0.7:  # 圆度筛选
                (x, y), radius = cv2.minEnclosingCircle(contour)
                bubbles.append({
                    "center": (int(x), int(y)),
                    "radius": int(radius),
                    "area": area,
                    "circularity": circularity
                })
    
    return bubbles
```

**验收标准**: 自动检测显微镜图片中的气泡并测量尺寸

### 3.2.3 OCR 文字提取
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| PaddleOCR | 中英文 OCR | 2d |
| 表格识别 | 识别图片中的表格 | 3d |
| 公式识别 | 识别数学公式 | 3d |
| 文字后处理 | 纠错和格式化 | 1d |

**验收标准**: 提取图片中的文字、表格、公式

### 3.2.4 图片描述生成
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| Vision API | Claude Vision 图片理解 | 2d |
| 描述生成 | 生成图片内容描述 | 1d |
| 关键词提取 | 提取图片关键词 | 1d |
| 描述存储 | 存储描述到数据库 | 1d |

**验收标准**: 自动生成图片内容描述

---

## 3.3 以图搜图

### 3.3.1 图片向量化
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| CLIP Embedding | 提取图片特征向量 | 2d |
| 向量存储 | pgvector 存储图片向量 | 1d |
| 索引优化 | HNSW 索引加速搜索 | 1d |
| 批量处理 | 批量提取历史图片向量 | 1d |

**验收标准**: 所有图片都有对应的特征向量

### 3.3.2 相似度搜索
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 以图搜图 | 上传图片搜索相似图片 | 2d |
| 文字搜图 | 输入文字描述搜索图片 | 2d |
| 混合搜索 | 图片+文字混合搜索 | 2d |
| 结果排序 | 按相似度排序 | 1d |

**验收标准**: 支持以图搜图和文字搜图

### 3.3.3 跨模态搜索
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 文字→图片 | 文字描述搜索图片 | 2d |
| 图片→文字 | 图片搜索相关文字 | 2d |
| 图片→公式 | 图片搜索相关公式 | 2d |
| 统一搜索 | 统一搜索入口 | 2d |

**验收标准**: 支持跨模态搜索

---

## 3.4 图片自动分类与标注

### 3.4.1 自动分类
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 分类模型 | 训练图片分类模型 | 3d |
| 类别定义 | 定义图片类别体系 | 1d |
| 自动分类 | 上传图片自动分类 | 2d |
| 分类修正 | 支持手动修正分类 | 1d |

**验收标准**: 图片上传后自动分类

### 3.4.2 自动标注
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 标签生成 | LLM 生成图片标签 | 2d |
| 标签管理 | 标签增删改查 | 1d |
| 标签搜索 | 按标签搜索图片 | 1d |
| 标签统计 | 标签使用统计 | 1d |

**验收标准**: 图片自动生成标签

### 3.4.3 智能相册
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 自动聚类 | 按内容自动聚类 | 2d |
| 相册生成 | 自动生成智能相册 | 2d |
| 时间线 | 按时间线浏览 | 1d |
| 地图视图 | 按位置浏览（如有 GPS） | 1d |

**验收标准**: 图片自动聚类形成智能相册

---

## 3.5 图片编辑与标注

### 3.5.1 在线编辑
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 裁剪旋转 | 基础图片编辑 | 2d |
| 亮度对比 | 调整亮度/对比度 | 1d |
| 滤镜效果 | 应用滤镜效果 | 1d |
| 编辑历史 | 编辑历史记录 | 1d |

**验收标准**: 支持在线图片编辑

### 3.5.2 标注工具
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 矩形标注 | 矩形框标注 | 2d |
| 圆形标注 | 圆形框标注 | 1d |
| 箭头标注 | 箭头指向标注 | 1d |
| 文字标注 | 文字说明标注 | 1d |
| 标注保存 | 保存标注结果 | 1d |

**验收标准**: 支持多种标注工具

### 3.5.3 图片对比
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 并排对比 | 两张图片并排对比 | 2d |
| 滑动对比 | 滑动条对比 | 2d |
| 差异高亮 | 高亮显示差异区域 | 2d |
| 动画切换 | 动画切换对比 | 1d |

**验收标准**: 支持多种图片对比方式

---

## 3.6 图片报告生成

### 3.6.1 图片集报告
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 图片选择 | 选择报告包含的图片 | 1d |
| 布局模板 | 多种布局模板 | 2d |
| 文字说明 | 添加文字说明 | 1d |
| 报告导出 | 导出为 PDF/PPT | 2d |

**验收标准**: 可生成图片集报告

### 3.6.2 实验图片报告
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 实验关联 | 关联到实验记录 | 1d |
| 自动生成 | 自动生成实验图片报告 | 2d |
| 图表结合 | 图片与数据图表结合 | 2d |
| 报告模板 | 实验图片报告模板 | 1d |

**验收标准**: 自动生成实验图片报告

---

## 数据库设计

```sql
-- 图片知识表
CREATE TABLE image_knowledge (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200),
    description TEXT,
    file_path VARCHAR(500),
    thumbnail_path VARCHAR(500),
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    format VARCHAR(20),
    
    -- 分类和标签
    category VARCHAR(100),
    tags TEXT[],
    image_type VARCHAR(50),  -- microscope/photo/screenshot/chart/diagram
    
    -- 分析结果
    ocr_text TEXT,
    ai_description TEXT,
    detected_objects JSONB,
    bubble_analysis JSONB,  -- 气泡分析结果
    
    -- 向量嵌入
    clip_embedding VECTOR(512),
    
    -- 关联
    experiment_id INTEGER REFERENCES experiments(id),
    project_id INTEGER REFERENCES projects(id),
    knowledge_id INTEGER REFERENCES knowledge(id),
    uploaded_by INTEGER REFERENCES members(id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 图片标注表
CREATE TABLE image_annotations (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES image_knowledge(id),
    annotation_type VARCHAR(20),  -- rect/circle/arrow/text
    coordinates JSONB,
    label VARCHAR(200),
    color VARCHAR(20),
    created_by INTEGER REFERENCES members(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 图片聚类表
CREATE TABLE image_clusters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    description TEXT,
    cluster_type VARCHAR(50),  -- auto/manual
    images INTEGER[],
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 实施步骤

### Week 1-2: 图片基础
- 图片上传与存储
- 图片预览与管理
- 图片压缩和缩略图

### Week 3: 图片分析
- CLIP 集成
- 图片分类
- OCR 文字提取
- 图片描述生成

### Week 4: 以图搜图
- 图片向量化
- 相似度搜索
- 跨模态搜索

### Week 5: 显微镜分析
- 气泡检测
- 尺寸测量
- 分布统计

### Week 6: 编辑与报告
- 图片编辑工具
- 标注工具
- 报告生成
