import type { ServiceMode, WorkbenchServiceMode } from './types';

export interface ServiceDefinition {
  id: WorkbenchServiceMode;
  label: string;
  description: string;
  helper: string;
  problemLabel?: string;
  codeLabel?: string;
  messageLabel: string;
  problemPlaceholder?: string;
  codePlaceholder?: string;
  messagePlaceholder: string;
  requiresProblem: boolean;
  requiresCode: boolean;
  example: {
    problemText: string;
    code: string;
    message: string;
  };
}

export const serviceCatalog: ServiceDefinition[] = [
  {
    id: 'debug',
    label: '代码纠错',
    description: '找出 C 代码里的常见错误',
    helper: '有代码但不知道哪里错',
    problemLabel: '题目（可选）',
    codeLabel: 'C 代码',
    messageLabel: '遇到的问题',
    problemPlaceholder: '可以粘贴题目描述，也可以先留空。',
    codePlaceholder: '#include <stdio.h>\n\nint main() {\n    int n;\n    scanf("%d", n);\n    printf("%d", n);\n    return 0;\n}',
    messagePlaceholder: '我这个代码为什么过不了？',
    requiresProblem: false,
    requiresCode: true,
    example: {
      problemText: '输入一个整数 n，输出 n。',
      code: '#include <stdio.h>\n\nint main() {\n    int n;\n    scanf("%d", n);\n    printf("%d", n);\n    return 0;\n}',
      message: '我这个代码为什么过不了？'
    }
  },
  {
    id: 'knowledge',
    label: '问知识',
    description: '直接问 C 语言语法或算法概念',
    helper: '没有代码也能问',
    messageLabel: '你想问什么',
    messagePlaceholder: 'scanf 为什么要加 &？',
    requiresProblem: false,
    requiresCode: false,
    example: {
      problemText: '',
      code: '',
      message: 'scanf 为什么要加 &？'
    }
  },
  {
    id: 'data',
    label: '问学习数据',
    description: '查看最近常错、薄弱点和掌握度',
    helper: '了解自己弱在哪里',
    messageLabel: '你想了解什么学习情况',
    messagePlaceholder: '我最近最常犯什么错误？',
    requiresProblem: false,
    requiresCode: false,
    example: {
      problemText: '',
      code: '',
      message: '我最近最常犯什么错误？'
    }
  },
  {
    id: 'hint',
    label: '分层提示',
    description: '不直接给答案，先给你一步提示',
    helper: '有题目但没思路',
    problemLabel: '题目内容',
    messageLabel: '希望怎么提示',
    problemPlaceholder: '输入题目描述、输入输出要求或样例。',
    messagePlaceholder: '我没思路，先别告诉答案，给点提示。',
    requiresProblem: true,
    requiresCode: false,
    example: {
      problemText: '输入 n 个整数，输出其中的最大值。',
      code: '',
      message: '我没思路，先别告诉答案，给点提示。'
    }
  },
  {
    id: 'problem',
    label: '题目拆解',
    description: '拆输入、处理、输出和边界',
    helper: '先看懂题再写代码',
    problemLabel: '题目内容',
    messageLabel: '哪里看不懂',
    problemPlaceholder: '粘贴完整题目，包含输入输出说明最好。',
    messagePlaceholder: '这个题目的输入、处理和输出分别是什么意思？',
    requiresProblem: true,
    requiresCode: false,
    example: {
      problemText: '输入 n 个整数，输出最大值和它第一次出现的位置。',
      code: '',
      message: '这个题目的输入、处理和输出分别是什么意思？'
    }
  },
  {
    id: 'review',
    label: '生成复盘',
    description: '把这次错误保存成错题档案',
    helper: '沉淀本轮学习',
    messageLabel: '复盘要求',
    messagePlaceholder: '帮我生成本次错误复盘。',
    requiresProblem: false,
    requiresCode: false,
    example: {
      problemText: '',
      code: '',
      message: '帮我生成本次错误复盘，下次怎么避免？'
    }
  }
];

export const followUpActions: Array<{ label: string; message: string; mode: ServiceMode }> = [
  { label: '再讲简单点', message: '再用更简单的话解释一下。', mode: 'followup' },
  { label: '举个例子', message: '能举一个更小的例子吗？', mode: 'followup' },
  { label: '为什么这样写', message: '为什么这里要这样写？', mode: 'followup' },
  { label: '给我一步提示', message: '先别给完整答案，只给下一步提示。', mode: 'followup' },
  { label: '我还是不懂', message: '我还是不懂，请换一种方式解释。', mode: 'followup' },
  { label: '生成复盘', message: '帮我生成本次错误复盘。', mode: 'review' }
];

export const serviceLabels: Record<ServiceMode, string> = {
  auto: '自动判断',
  knowledge: '问知识',
  problem: '题目拆解',
  hint: '分层提示',
  debug: '代码纠错',
  data: '问学习数据',
  review: '生成复盘',
  followup: '继续追问'
};

export function getServiceDefinition(mode: ServiceMode): ServiceDefinition {
  return serviceCatalog.find((service) => service.id === mode) ?? serviceCatalog[0];
}
