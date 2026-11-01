"""Documentation-only interactions for Evolve design 0.6.2; no plugin logic."""

import json

SEQUENCES = json.loads(r'''[
  {
    "number": 1,
    "name": "01-system-architecture.svg",
    "title": "Evolve：项目理解与工作闭环",
    "subtitle": "0.6.2 · 八个 Skill 共用内核；单项目积累，多任务续接",
    "source": "design.md#architecture",
    "lanes": [
      "用户／宿主",
      "workflow 路由",
      "职责 Skill",
      "内核／项目资料"
    ],
    "events": [
      [
        0,
        1,
        "目标、限制与当前意图"
      ],
      [
        1,
        3,
        "读取目标任务、共享知识与现场变化"
      ],
      [
        3,
        1,
        "返回来源、适用性与冲突",
        "return"
      ],
      {
        "section": "八个职责：workflow / init / propose / apply / verify / archive / learn / maintain"
      },
      [
        1,
        2,
        "按授权与复杂度调用唯一负责者"
      ],
      [
        2,
        3,
        "短方案或 spec、任务、成果、验证及必要恢复",
        "green"
      ],
      {
        "section": "Markdown：正式含义；SQLite：任务与事实；证据：来源；视图：按需展示"
      },
      [
        2,
        0,
        "返回实际结果、验证覆盖和待审知识差异",
        "return"
      ],
      {
        "section": "部署与个人库退出；正式数据写入按具体授权；不自动调度多代理"
      }
    ]
  },
  {
    "number": 2,
    "name": "02-end-to-end-workflow.svg",
    "title": "按意图与复杂度推进",
    "subtitle": "梳理深度独立判断；完整请求内连续实施与验证",
    "source": "workflows.md#common",
    "lanes": [
      "用户",
      "规划／分析",
      "实施／验证",
      "记录／知识"
    ],
    "events": [
      [
        0,
        1,
        "提出工作目标；恢复相关上下文"
      ],
      {
        "section": "没有明确修改请求：先调查和方案，等待确认，不执行修复"
      },
      [
        1,
        0,
        "简单：简短方案；复杂：spec 与依赖任务",
        "return"
      ],
      [
        0,
        2,
        "明确修改授权；复杂方案整体确认后推进"
      ],
      [
        2,
        3,
        "逐项结果、失败尝试与相关检查",
        "green"
      ],
      [
        3,
        2,
        "反馈当前依据及待修正问题",
        "return"
      ],
      [
        2,
        0,
        "实现与验收结果；待确认知识另列",
        "return"
      ],
      {
        "section": "完整请求：按需测试与双维审查；修复由 apply，复查由 verify；不自动提交"
      },
      {
        "section": "事实可封存；正式知识确认后才应用；无部署阶段"
      }
    ]
  },
  {
    "number": 3,
    "name": "03-command-and-next-step.svg",
    "title": "统一入口、授权与分派",
    "subtitle": "十四顶层动作，八个唯一 owner；查询和完整工作请求分开",
    "source": "workflows.md#commands",
    "lanes": [
      "用户／宿主",
      "workflow",
      "负责 Skill",
      "共享内核"
    ],
    "events": [
      [
        0,
        1,
        "显式动作或自然语言；定位目标"
      ],
      [
        1,
        3,
        "规范方法、范围、授权和来源"
      ],
      {
        "section": "未知动作／方法不降级默认执行；无动作只读 status；release 已退出"
      },
      [
        3,
        1,
        "纯查询返回当前状态，不创建 run",
        "return"
      ],
      [
        1,
        2,
        "明确写请求交唯一 owner"
      ],
      [
        2,
        3,
        "start → 子操作 → finish",
        "green"
      ],
      [
        2,
        0,
        "当前结果与合法下一步",
        "return"
      ],
      {
        "section": "apply 单阶段不隐含整体验收；完整实现测试请求可连续调用 verify"
      }
    ]
  },
  {
    "number": 4,
    "name": "04-init-new-and-existing.svg",
    "title": "接入与自适应项目梳理",
    "subtitle": "先整包安装并按项目启用，再明确接入；安装不创建业务记录",
    "source": "workflows.md#init",
    "lanes": [
      "用户／宿主",
      "宿主安装器",
      "init／规划",
      "项目资料"
    ],
    "events": [
      [
        0,
        1,
        "安装同版本完整包并定位共享资源"
      ],
      [
        1,
        0,
        "包版本、实际启用范围和缺失条件",
        "return"
      ],
      {
        "section": "安装与 doctor 不建库；重复渠道先诊断；宿主管包，init 不自我升级"
      },
      [
        0,
        2,
        "明确项目接入与当前工作"
      ],
      [
        2,
        3,
        "发现已有资料、规则、检查入口及缺口"
      ],
      [
        3,
        2,
        "已覆盖范围和需补依据",
        "return"
      ],
      [
        2,
        3,
        "增量接入与事实留档，保留既有内容",
        "green"
      ],
      [
        2,
        0,
        "呈现具体初始正式基线候选",
        "return"
      ],
      [
        0,
        2,
        "批准具体内容"
      ],
      [
        2,
        3,
        "核基线后应用并登记",
        "green"
      ],
      {
        "section": "升级不迁移项目库；卸载保留资料；不生成业务骨架或强制全量访谈"
      }
    ]
  },
  {
    "number": 5,
    "name": "05-propose-and-update.svg",
    "title": "方案、spec 与任务拆分",
    "subtitle": "每项交付窄而完整的行为；只列真实阻塞条件，不按技术层排队",
    "source": "workflows.md#propose",
    "lanes": [
      "用户",
      "propose",
      "上下文／现场",
      "REV／任务"
    ],
    "events": [
      [
        0,
        1,
        "提出目标或要求修订"
      ],
      [
        1,
        2,
        "复用相关知识与经验，核对适用性"
      ],
      [
        2,
        1,
        "事实、候选线索和关键问题",
        "return"
      ],
      [
        1,
        3,
        "短方案快照或 spec、AC 与依赖任务",
        "green"
      ],
      {
        "section": "任务 = 用户结果 + 验证办法 + 真实前置 + 来源／范围；必要内核随切片实现"
      },
      [
        1,
        0,
        "呈现具体内容和验证安排",
        "return"
      ],
      [
        0,
        1,
        "复杂方案整体确认；简单修改沿有效授权"
      ],
      [
        1,
        3,
        "记录接受来源与具体版本",
        "green"
      ],
      {
        "section": "update 只重开受影响的完成定义；旧事实保留，重大新方案重新确认"
      },
      {
        "section": "广泛迁移：兼容扩展 → 分批迁移 → 清理／集成；不伪称每批独立完整通过"
      }
    ]
  },
  {
    "number": 6,
    "name": "06-apply-task-execution.svg",
    "title": "按依赖实施与任务留档",
    "subtitle": "范围内连续推进；相关冲突协调，无关工作可继续",
    "source": "workflows.md#apply",
    "lanes": [
      "用户",
      "apply",
      "内核／依赖",
      "成果／检查"
    ],
    "events": [
      [
        0,
        1,
        "明确实施目标与范围"
      ],
      [
        1,
        2,
        "核对 REV、授权、前置与资源占用"
      ],
      [
        2,
        1,
        "可推进任务及相关阻碍",
        "return"
      ],
      {
        "section": "缺陷先保存症状判据与实际观察；apply 修正后由 verify 原判据复验"
      },
      [
        1,
        3,
        "写前核现场，形成约定成果",
        "green"
      ],
      [
        3,
        1,
        "实际改动与任务级检查",
        "return"
      ],
      [
        1,
        2,
        "记录定义摘要、结果、证据与失败尝试",
        "green"
      ],
      {
        "section": "同 Change 写入协调串行；外部编辑差异不覆盖；重大方案变化回 propose"
      },
      {
        "section": "同 REV 验收失败：有修改授权时重开相关任务；缺补测交 apply，不为修缺陷强造新需求"
      },
      [
        1,
        0,
        "完成范围和后续验证；完整请求内继续",
        "return"
      ]
    ]
  },
  {
    "number": 7,
    "name": "07-verify-and-evidence.svg",
    "title": "按影响验证与完成判定",
    "subtitle": "测试与代码审查分别给依据；自审不冒充独立审查，缺证据不当通过",
    "source": "workflows.md#verify",
    "lanes": [
      "规划／用户",
      "verify",
      "实际现场",
      "证据／结果"
    ],
    "events": [
      [
        0,
        1,
        "AC、行为测试入口、项目规范及范围"
      ],
      [
        1,
        2,
        "固定实际成果与对照点，包含相关未提交内容"
      ],
      [
        2,
        1,
        "现场摘要、归属和检查条件",
        "return"
      ],
      [
        1,
        3,
        "运行相关测试、回归和适用症状复验",
        "green"
      ],
      [
        1,
        3,
        "审查规格符合性及规范／职责和维护性",
        "green"
      ],
      {
        "section": "必需缺陷未解决不能通过；主观建议可延期，须说明依据与影响"
      },
      [
        3,
        1,
        "逐项结果、发现、处置与复查证据",
        "return"
      ],
      [
        1,
        0,
        "结果／范围／限制；缺口交 apply 在授权内修正",
        "return"
      ],
      {
        "section": "只 verify 不修改代码、测试或任务实施状态；短方案也可作规格依据"
      },
      {
        "section": "候选检查不等于目标已应用；现场改变重核，不只看旧 passed"
      }
    ]
  },
  {
    "number": 8,
    "name": "08-sync-and-archive.svg",
    "title": "成果封存与正式知识确认",
    "subtitle": "附带知识可待审；正式文档本身是交付物时必须应用并验证",
    "source": "workflows.md#archive",
    "lanes": [
      "用户",
      "archive／sync",
      "事实／验证",
      "正式知识"
    ],
    "events": [
      {
        "section": "路径 A：开发已完成，知识更新只是附带改进"
      },
      [
        1,
        2,
        "重新核对必需成果、最新验收和现场"
      ],
      [
        2,
        1,
        "当前有效完成依据",
        "return"
      ],
      [
        1,
        2,
        "封存指定截点；待审知识另列",
        "green"
      ],
      {
        "section": "路径 B：用户要求交付正式文档／规则，不能只封存候选"
      },
      [
        1,
        0,
        "呈现具体差异与候选内容检查",
        "return"
      ],
      [
        0,
        1,
        "批准具体候选与目标"
      ],
      [
        1,
        3,
        "由 init / sync / learn 应用批准内容",
        "green"
      ],
      [
        3,
        2,
        "verify 核实际字节与适用检查",
        "green"
      ],
      [
        2,
        1,
        "实际成果满足要求后才封存",
        "return"
      ],
      {
        "section": "同批非冲突修改复用批准证明链；旧延期提案被替代后不应用"
      }
    ]
  },
  {
    "number": 9,
    "name": "09-authorized-data-operations.svg",
    "title": "正式环境数据操作与未知结果",
    "subtitle": "默认只读／测试；具体授权后才执行正式数据修改",
    "source": "runtime.md#external-effects",
    "lanes": [
      "用户",
      "apply",
      "本地操作／占用",
      "外部目标"
    ],
    "events": [
      {
        "section": "批准绑定入口及间接 SQL／脚本／参数和真实目标；无法固定实际范围不执行"
      },
      [
        1,
        0,
        "环境、范围、具体脚本、验证及补偿方案",
        "return"
      ],
      [
        0,
        1,
        "批准同一内容版本与目标"
      ],
      [
        1,
        2,
        "先登记操作、授权、幂等键与未决保护",
        "green"
      ],
      [
        1,
        3,
        "事务外执行具体候选",
        "green"
      ],
      {
        "section": "超时或回执丢失：effect_outcome=unknown；保留相关占用，不换 ID 重发"
      },
      [
        1,
        3,
        "reconcile 仅核实原操作"
      ],
      [
        3,
        1,
        "确证或仍未知；查询失败不抹旧事实",
        "return"
      ],
      [
        1,
        2,
        "追加观察与业务验证；确证后解除占用",
        "green"
      ],
      {
        "section": "补偿另有候选与授权；恢复旧档案不能清除未决保护；无 REL／部署状态"
      },
      {
        "section": "取消任务或 failed 不证明外部未执行；已知部分效果与未核范围分别保留"
      }
    ]
  },
  {
    "number": 10,
    "name": "10-resume-and-recover.svg",
    "title": "多任务续接与现场变化",
    "subtitle": "共享项目知识，隔离任务进度；恢复不自动执行",
    "source": "workflows.md#multitask",
    "lanes": [
      "用户／会话",
      "workflow／owner",
      "项目历史",
      "现场／资源"
    ],
    "events": [
      {
        "section": "正常暂停：owner 保存 partial 结果、剩余工作及授权，释放安全结束的本地写段"
      },
      [
        0,
        1,
        "指定主题或任务继续"
      ],
      [
        1,
        2,
        "读取对应 Change／分析链及项目级阻碍"
      ],
      [
        1,
        3,
        "核对相关文件、共享接口、依赖与占用"
      ],
      [
        3,
        1,
        "外部差异、冲突和时效限制",
        "return"
      ],
      {
        "section": "只 resume 展示不写；明确继续才登记可核实变化与新 run"
      },
      [
        1,
        2,
        "分别记录 A／B 任务，不用最近聊天作身份",
        "green"
      ],
      [
        1,
        0,
        "重叠范围协调；无关任务继续",
        "return"
      ],
      {
        "section": "正常封存直接续接；异常未封存才恢复；宿主活着不等于该 run 仍占有写权"
      }
    ]
  },
  {
    "number": 11,
    "name": "11-history-export-and-restore.svg",
    "title": "档案备份、恢复集合与防重放",
    "subtitle": "受管档案恢复不回退业务源码或真实数据",
    "source": "runtime.md#recovery",
    "lanes": [
      "用户",
      "maintain",
      "保护清单／控制区",
      "档案／证据"
    ],
    "events": [
      [
        0,
        1,
        "明确备份或恢复源"
      ],
      {
        "section": "备份固定数据库检查点和不可变引用版本；未登记手改单列保护附录，不拼接假一致包"
      },
      [
        1,
        3,
        "检查同项目、摘要与必要附件"
      ],
      [
        1,
        2,
        "保护当前现场、旧历史和外部未决引用",
        "green"
      ],
      {
        "section": "restore 先设维护屏障，排空仍可写／派发的旧本地执行者，再换库；未知外部效果仍保留"
      },
      {
        "section": "包外受管文件保护隔离；未登记用户文件保留，路径冲突先处理"
      },
      [
        1,
        3,
        "按清单替换受管集合，核实字节",
        "green"
      ],
      [
        1,
        2,
        "切换 epoch、登记恢复，拒绝旧写请求",
        "green"
      ],
      [
        1,
        0,
        "汇报恢复范围、现场差异和外部待核实",
        "return"
      ],
      {
        "section": "不执行恢复包脚本；unknown 由 apply 核实；容量预检，不递归备份"
      },
      {
        "section": "包更新与档案恢复分开：固定运行版本或安全结束；卸载不删除项目和未决保护"
      }
    ]
  },
  {
    "number": 12,
    "name": "12-learning-and-promotion.svg",
    "title": "项目内经验、反馈与集中审阅",
    "subtitle": "候选只作线索；证据强度不等于正式规则权威",
    "source": "workflows.md#learning",
    "lanes": [
      "阶段 Skill",
      "learn",
      "项目经验／依据",
      "用户／规则"
    ],
    "events": [
      [
        0,
        1,
        "检索相关经验和历史反例"
      ],
      [
        1,
        2,
        "过滤来源、条件、版本与状态"
      ],
      [
        2,
        0,
        "少量相关线索；候选明确标注",
        "return"
      ],
      [
        0,
        1,
        "记录是否采用、对应结果和归因限制",
        "green"
      ],
      [
        1,
        2,
        "追加支持／反例，不抹旧记录",
        "green"
      ],
      [
        1,
        3,
        "集中呈现具体规则差异与影响",
        "return"
      ],
      [
        3,
        1,
        "接受、拒绝或延期"
      ],
      [
        1,
        2,
        "仅批准版本应用并建立规则关联",
        "green"
      ],
      {
        "section": "反例影响后续方案与规则复审；不自动改正文；无个人库或模型训练"
      },
      {
        "section": "机械问题先提复用／新增检查；获修改授权后走 apply / verify，不由 learn 改 CI"
      },
      {
        "section": "M1 即实际产生候选 → 下次检索／核实 → 采用或拒绝及反馈，不只读取预置经验"
      }
    ]
  },
  {
    "number": 13,
    "name": "13-object-and-trace-model.svg",
    "title": "领域、执行与表示的职责",
    "subtitle": "工作完成、验收通过、知识批准及落盘分别表达",
    "source": "design.md#domain",
    "lanes": [
      "项目／正式知识",
      "Change／Task",
      "验证／经验",
      "run／operation"
    ],
    "events": [
      [
        0,
        1,
        "目标、约束、基线与未来方案"
      ],
      [
        1,
        2,
        "成果、实际范围和完成条件"
      ],
      [
        2,
        1,
        "证据、失败及适用性反馈",
        "return"
      ],
      [
        1,
        3,
        "REV、任务进度与关键事件",
        "green"
      ],
      [
        2,
        3,
        "验证记录、经验采用及反例",
        "green"
      ],
      {
        "section": "独立分析使用 run 链，不伪造 Change；用户任务列表聚合变更和分析主题"
      },
      {
        "section": "Markdown 管正式含义；SQLite 管结构化事实；证据保存来源；视图按需生成"
      },
      [
        3,
        0,
        "批准的具体知识差异才应用",
        "green"
      ],
      {
        "section": "Release 已移出；operation 不是业务对象或用户审批步骤"
      }
    ]
  },
  {
    "number": 14,
    "name": "14-lightweight-and-cancel.svg",
    "title": "轻量任务、升级与停止",
    "subtitle": "材料随复杂度调整；取消不删除已做事实",
    "source": "workflows.md#states",
    "lanes": [
      "用户",
      "规划／实施",
      "记录与方案",
      "成果／证据"
    ],
    "events": [
      [
        0,
        1,
        "明确简单修改"
      ],
      [
        1,
        0,
        "简述范围、做法与检查",
        "return"
      ],
      [
        1,
        2,
        "保存短方案正文和授权",
        "green"
      ],
      [
        1,
        3,
        "实施和相关验证",
        "green"
      ],
      {
        "section": "发现复杂度升级：复用材料，生成 spec／任务清单并确认"
      },
      [
        0,
        1,
        "修改范围或停止工作"
      ],
      [
        1,
        2,
        "新 REV 或取消记录；保留旧结果",
        "green"
      ],
      {
        "section": "范围缩减需接受；取消 Task 不自动豁免 AC；停止不自动回退用户源码"
      }
    ]
  },
  {
    "number": 15,
    "name": "15-skill-handoff-and-rotation.svg",
    "title": "统一执行与结果承接",
    "subtitle": "一个 run 保存输入核查和封存结果，无独立交接回执",
    "source": "runtime.md#execution",
    "lanes": [
      "负责 Skill",
      "共享内核",
      "历史／证据",
      "后继 Skill"
    ],
    "events": [
      [
        0,
        1,
        "prepare 规范动作、范围、来源及授权"
      ],
      [
        1,
        2,
        "start 短事务核版本／epoch，建立 run",
        "green"
      ],
      [
        0,
        1,
        "execute 按稳定 operation 保存实际进度"
      ],
      [
        1,
        2,
        "finish 提交结果与摘要",
        "green"
      ],
      [
        2,
        3,
        "source_runs 引用原封存结果",
        "return"
      ],
      [
        3,
        1,
        "重核当前语义、范围和后续纠正"
      ],
      {
        "section": "同请求重试返回原事实；终态 run 不重开；旧 epoch 不重放"
      },
      {
        "section": "present 需要报告才调用独立 export；视图失败不重做业务"
      },
      {
        "section": "本轮 partial 可正常 finish；外部 unknown 占用独立保留；档案维护前排空本地写者"
      }
    ]
  },
  {
    "number": 16,
    "name": "16-analysis-and-explanation.svg",
    "title": "独立调查、续查与转修复",
    "subtitle": "先寻找能识别症状的可重复观察；无修改授权时止于调查与方案",
    "source": "workflows.md#analysis",
    "lanes": [
      "用户",
      "propose analyze",
      "资料／证据",
      "分析链／修复"
    ],
    "events": [
      [
        0,
        1,
        "问题、范围和调查目标"
      ],
      [
        1,
        2,
        "按允许范围固定输入、环境、独立预期和观察方法"
      ],
      [
        2,
        1,
        "观察、假设及未覆盖部分",
        "return"
      ],
      {
        "section": "无法复现可保留假设与限制；偶发问题记次数／失败数，不补造 red 或根因"
      },
      [
        1,
        3,
        "及时保存过程和封存本轮结果",
        "green"
      ],
      [
        1,
        0,
        "回答、限制与可选修复方案",
        "return"
      ],
      {
        "section": "换会话恢复同主题；新日期写新输入；同链一个后继，不同主题可并存"
      },
      [
        0,
        1,
        "明确确认执行修复"
      ],
      [
        1,
        3,
        "匹配或创建 Change；引用分析作为来源",
        "green"
      ],
      {
        "section": "来源不等于方案接受或验收通过；报告重导不重新调查"
      },
      {
        "section": "获准修复后按同一有效判据复验；不删断言换通过，不擅加生产探针"
      }
    ]
  },
  {
    "number": 17,
    "name": "17-data-scenarios.svg",
    "title": "数据开发、排查与血缘共用流程",
    "subtitle": "业务日期、口径、粒度和覆盖按需记录，不建专属平台",
    "source": "scenarios.md#data-development",
    "lanes": [
      "用户",
      "规划／分析",
      "实施／验证",
      "事实／知识"
    ],
    "events": [
      [
        0,
        1,
        "明确是调查、开发还是实际数据修改"
      ],
      {
        "section": "SQL／模型开发：口径清楚后形成方案，复杂任务整体确认"
      },
      [
        1,
        2,
        "形成成果并按范围对账／检查"
      ],
      [
        2,
        3,
        "记录实际方法、日期、覆盖与限制",
        "green"
      ],
      {
        "section": "数据异常／血缘：保存来源与观察底稿，不自动修改数据或正式知识"
      },
      [
        1,
        3,
        "候选发现和同源图文输出",
        "green"
      ],
      [
        3,
        0,
        "结果及集中待审知识差异",
        "return"
      ],
      {
        "section": "正式数据写入另核具体授权；只提交脚本不等于补数完成；没有部署步骤"
      }
    ]
  }
]''')
