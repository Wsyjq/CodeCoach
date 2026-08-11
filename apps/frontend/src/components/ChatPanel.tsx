import { SendHorizonal } from 'lucide-react';
import { useState } from 'react';
import { followUpActions, serviceLabels } from '../lib/serviceCatalog';
import type { ChatResponse, ConversationTurn, Intent, ServiceMode } from '../lib/types';

const knowledgeLabels: Record<string, string> = {
  MEMORIZE: '先记住',
  UNDERSTAND: '要理解',
  MIXED: '先记再懂',
  UNKNOWN: '待判断'
};

const intentLabels: Record<Intent, string> = {
  KNOWLEDGE_QA: '知识讲解',
  DATA_QA: '学习数据分析',
  DEBUG_CODE: '代码纠错',
  NEED_HINT: '分层提示',
  REVIEW_SUMMARY: '错题复盘',
  UNDERSTAND_PROBLEM: '题目拆解'
};

export function ChatPanel({
  turns,
  loading,
  disabled = false,
  onFollowUp
}: {
  turns: ConversationTurn[];
  loading: boolean;
  disabled?: boolean;
  onFollowUp: (message: string, mode: ServiceMode) => void | Promise<void>;
}) {
  const [followUp, setFollowUp] = useState('');
  const [localError, setLocalError] = useState('');
  const latestResponse = [...turns].reverse().find((turn) => turn.role === 'assistant' && turn.response)?.response;
  const actions = latestResponse?.next_actions.length ? latestResponse.next_actions : followUpActions;

  async function submitFollowUp(message: string, mode: ServiceMode = 'followup') {
    if (loading) return;
    if (disabled) {
      setLocalError('当前处于维护模式，追问服务暂不可用。');
      return;
    }
    const trimmed = message.trim();
    if (!trimmed) {
      setLocalError('请输入要继续追问的内容。');
      return;
    }
    setLocalError('');
    await onFollowUp(trimmed, mode);
    setFollowUp('');
  }

  return (
    <section className="panel answer-panel">
      <div className="panel-heading">
        <span>多轮辅导对话</span>
        <span className="mini-label">{latestResponse?.conversation_title || 'CodeCoach'}</span>
      </div>

      {turns.length === 0 ? (
        <div className="empty-chat">
          <span className="mini-label">等待开始</span>
          <strong>先在左侧选择一个学习服务。</strong>
          <p>你可以直接问知识、查学习数据，也可以粘贴 C 代码让 CodeCoach 帮你定位错误。</p>
        </div>
      ) : (
        <div className="conversation-list">
          {turns.map((turn) => (
            <article className={`turn-card ${turn.role}`} key={turn.id}>
              {turn.role === 'user' ? (
                <>
                  <span className="mini-label">{serviceLabels[turn.mode ?? 'auto']}</span>
                  <p>{turn.message}</p>
                </>
              ) : turn.response ? (
                <AssistantResponse response={turn.response} mode={turn.mode} />
              ) : null}
            </article>
          ))}
        </div>
      )}

      {loading ? (
        <div className="teaching-skeleton">
          <span />
          <span />
          <span />
        </div>
      ) : null}

      <div className="followup-panel">
        <div className="quick-followups">
          {actions.map((action) => (
            <button
              className="ghost-button"
              key={`${action.label}-${action.message}`}
              type="button"
              onClick={() => submitFollowUp(action.message, action.mode)}
              disabled={disabled || loading || turns.length === 0}
            >
              {action.label}
            </button>
          ))}
        </div>
        <div className="followup-input-row">
          <input
            value={followUp}
            onChange={(event) => {
              setFollowUp(event.target.value);
              if (event.target.value.trim()) setLocalError('');
            }}
            placeholder="继续追问刚才的问题..."
            disabled={disabled || loading || turns.length === 0}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                submitFollowUp(followUp, 'followup');
              }
            }}
          />
          <button
            className="icon-button"
            type="button"
            aria-label="发送追问"
            onClick={() => submitFollowUp(followUp, 'followup')}
            disabled={disabled || loading || turns.length === 0}
          >
            <SendHorizonal size={18} />
          </button>
        </div>
        {localError ? <div className="form-error">{localError}</div> : null}
      </div>
    </section>
  );
}

function AssistantResponse({ response, mode }: { response: ChatResponse; mode?: ServiceMode }) {
  const teaching = buildTeachingNotes(response);

  return (
    <div className="assistant-response">
      <div className="answer-meta-row">
        <span className="status-pill">{mode ? serviceLabels[mode] : intentLabels[response.intent]}</span>
        <span className={`badge type-${response.knowledge_type.toLowerCase()}`}>学习策略：{knowledgeLabels[response.knowledge_type]}</span>
      </div>

      {response.knowledge_tags.length ? (
        <div className="tag-row compact-tags">
          {response.knowledge_tags.map((tag) => (
            <span className="tag" key={tag}>{tag}</span>
          ))}
        </div>
      ) : null}

      <div className="teaching-card">
        <div className="teaching-section conclusion">
          <span className="mini-label">一句话结论</span>
          <strong>{teaching.conclusion}</strong>
        </div>
        <div className="teaching-section">
          <span className="mini-label">为什么</span>
          <p className="answer-text">{teaching.explanation}</p>
        </div>
        <div className="insight-grid">
          <div className="insight-card warning">
            <span className="mini-label">容易误解</span>
            <p>{teaching.pitfall}</p>
          </div>
          <div className="insight-card next">
            <span className="mini-label">下一步</span>
            <p>{teaching.nextStep}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildTeachingNotes(response: ChatResponse) {
  const paragraphs = response.answer
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);
  const conclusion = paragraphs[0] || response.answer || '等待输入后生成讲解。';
  const explanation = paragraphs.length > 1 ? paragraphs.slice(1).join('\n\n') : conclusion;

  return {
    conclusion,
    explanation,
    pitfall: getPitfall(response),
    nextStep: getNextStep(response)
  };
}

function getPitfall(response: ChatResponse) {
  if (response.intent === 'DEBUG_CODE') {
    return '先定位最小出错行，再判断是语法规则、边界条件，还是算法思路问题。';
  }
  if (response.intent === 'DATA_QA') {
    return '问数结果只代表当前学习记录，不要把单次统计当成长期掌握情况。';
  }
  if (response.intent === 'NEED_HINT') {
    return '提示不是答案，先把输入、处理、输出三步自己写下来。';
  }
  if (response.knowledge_type === 'MEMORIZE') {
    return '记忆型知识先背固定规则，再用 1-2 个小例子确认用法。';
  }
  return '理解型知识不要只记结论，要能说清楚为什么这样做。';
}

function getNextStep(response: ChatResponse) {
  if (response.intent === 'DEBUG_CODE') {
    return '按提示只改一处代码，重新运行，再决定是否需要生成复盘。';
  }
  if (response.intent === 'DATA_QA') {
    return '优先复习出现次数最多、掌握度最低的知识标签。';
  }
  if (response.intent === 'NEED_HINT') {
    return '先实现最小版本，通过样例后再处理边界情况。';
  }
  if (response.intent === 'REVIEW_SUMMARY') {
    return '用自己的话复述错误原因，并记录下次检查信号。';
  }
  return '换一道同类小题，把这条规则立即用一次。';
}
