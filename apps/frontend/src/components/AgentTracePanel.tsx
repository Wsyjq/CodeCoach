import type { AgentTraceItem, ChatResponse } from '../lib/types';

const pipeline = [
  {
    label: '确认学习水平',
    aliases: ['Profile Agent'],
    idle: '等待读取用户水平'
  },
  {
    label: '判断本次任务',
    aliases: ['Intent Router'],
    idle: '等待判断服务类型'
  },
  {
    label: '查知识和记录',
    aliases: ['RAG Agent', 'Data Query Tool', 'Code Analyzer', 'RAG / Tool', 'Similarity Agent'],
    idle: '等待查询知识库或学习记录'
  },
  {
    label: '生成辅导策略',
    aliases: ['Debug Agent', 'Hint Agent', 'Problem Parser', 'Data Query Tool', 'Code Analyzer', 'Debug / Hint / Data'],
    idle: '等待生成讲解路径'
  },
  {
    label: '整理错题档案',
    aliases: ['Review Agent'],
    idle: '等待生成复盘卡片'
  },
  {
    label: '保存学习记忆',
    aliases: ['Memory Agent', 'Review / Memory'],
    idle: '等待写入长期记忆'
  }
];

export function AgentTracePanel({ response, loading, userLabel }: { response: ChatResponse; loading: boolean; userLabel: string }) {
  const steps = pipeline.map((step, index) => resolveStep(step, index, response, loading, userLabel));

  return (
    <aside className="panel trace-panel">
      <div className="panel-heading">
        <span>系统分析过程</span>
        <span className="mini-label">透明进度</span>
      </div>
      <div className="trace-list">
        {steps.map((item, index) => (
          <div className={`trace-item ${item.status}`} key={`${item.node}-${index}`}>
            <span className="trace-index">{index + 1}</span>
            <span className={`trace-dot ${item.status}`} />
            <div>
              <div className="trace-node">{item.node}</div>
              <div className="trace-detail">{item.detail}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="diagnosis-card">
        <div className="mini-label">当前进度</div>
        <p>{getDiagnosis(response)}</p>
      </div>
    </aside>
  );
}

function resolveStep(
  step: { label: string; aliases: string[]; idle: string },
  index: number,
  response: ChatResponse,
  loading: boolean,
  userLabel: string
): AgentTraceItem {
  if (loading) {
    if (index === 0) return { node: step.label, status: 'done', detail: userLabel };
    if (index === 1) return { node: step.label, status: 'running', detail: '正在识别意图' };
    return { node: step.label, status: 'waiting', detail: step.idle };
  }

  const matched = response.agent_trace.find((item) =>
    step.aliases.some((alias) => item.node === alias || item.node.includes(alias))
  );

  if (matched) {
    return {
      node: step.label,
      status: matched.status,
      detail: matched.detail || step.idle
    };
  }

  if (step.label === '整理错题档案' && response.review_card.id) {
    return { node: step.label, status: 'done', detail: response.review_card.title || '复盘卡片已生成' };
  }

  if (step.label === '保存学习记忆' && response.review_card.id) {
    return { node: step.label, status: 'done', detail: '已准备写入记忆库' };
  }

  if (step.label === '保存学习记忆' && response.similar_memory.matched) {
    return { node: step.label, status: 'warning', detail: response.similar_memory.title || '命中相似记忆' };
  }

  return { node: step.label, status: 'waiting', detail: step.idle };
}

function getDiagnosis(response: ChatResponse) {
  if (response.intent === 'DEBUG_CODE') {
    return '当前是代码纠错服务，系统会先定位错误，再结合知识点和历史错题给出讲解。';
  }
  if (response.intent === 'DATA_QA') {
    return '当前是学习数据服务，回答会优先参考统计、错题记忆和待复习任务。';
  }
  if (response.intent === 'NEED_HINT') {
    return '当前是分层提示服务，目标是给下一步思路，而不是直接给完整答案。';
  }
  if (response.intent === 'REVIEW_SUMMARY') {
    return '当前是复盘服务，重点沉淀错误类型、记忆点和下次复习建议。';
  }
  return `当前相关知识：${response.knowledge_tags.join(' / ') || '等待生成'}。`;
}
