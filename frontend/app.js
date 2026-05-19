/**
 * repo2prompt - Command Builder
 * 状态管理、命令生成、验证、预设系统
 */

// ============================================
// API 基础路径
// ============================================
// 如果是通过 file:// 协议打开，使用 localhost:8000
const API_BASE = window.location.protocol === 'file:'
  ? 'http://localhost:8000'
  : '';

// ============================================
// 状态管理
// ============================================
const state = {
  path: '.',
  output: '',
  exclude: [],
  copy: false,
  noSummary: false,
  interactive: false,
  verbose: 0,
  logLevel: '',
  model: '',
  apiKey: '',
  baseUrl: '',
  temperature: 0.3,
  maxWorkers: 5,
  maxLines: null,
  outlineOnly: false,
  outlineThreshold: null,
  showTokens: false,
  tokenModel: ''
};

// ============================================
// 内置预设
// ============================================
const BUILTIN_PRESETS = {
  'quick-scan': {
    name: 'Quick Scan',
    state: {
      noSummary: true,
      copy: true
    }
  },
  'full-summary': {
    name: 'Full Summary',
    state: {
      model: 'gpt-4o-mini',
      copy: true
    }
  },
  'outline-only': {
    name: 'Outline Only',
    state: {
      outlineOnly: true,
      noSummary: true,
      copy: true
    }
  },
  'debug-mode': {
    name: 'Debug Mode',
    state: {
      noSummary: true,
      verbose: 2,
      showTokens: true
    }
  }
};

// ============================================
// DOM 元素引用
// ============================================
const elements = {};

// ============================================
// 初始化
// ============================================
function initApp() {
  // 获取所有 DOM 元素
  cacheElements();

  // 绑定事件监听
  bindEvents();

  // 加载保存的状态
  loadSavedState();

  // 应用初始状态到 UI
  applyStateToUI();

  // 生成初始命令
  updateCommand();
}

function cacheElements() {
  // 路径
  elements.path = document.getElementById('path');

  // 通用选项
  elements.output = document.getElementById('output');
  elements.excludeInput = document.getElementById('exclude-input');
  elements.addExcludeBtn = document.getElementById('add-exclude-btn');
  elements.excludeTags = document.getElementById('exclude-tags');
  elements.copy = document.getElementById('copy');
  elements.noSummary = document.getElementById('no-summary');
  elements.interactive = document.getElementById('interactive');

  // 日志控制
  elements.verboseRadios = document.querySelectorAll('input[name="verbose"]');
  elements.logLevel = document.getElementById('log-level');

  // LLM 选项
  elements.model = document.getElementById('model');
  elements.apiKey = document.getElementById('api-key');
  elements.toggleApiKey = document.getElementById('toggle-api-key');
  elements.baseUrl = document.getElementById('base-url');
  elements.temperature = document.getElementById('temperature');
  elements.temperatureValue = document.getElementById('temperature-value');
  elements.maxWorkers = document.getElementById('max-workers');

  // 输出控制
  elements.maxLines = document.getElementById('max-lines');
  elements.outlineOnly = document.getElementById('outline-only');
  elements.outlineThreshold = document.getElementById('outline-threshold');

  // Token 预估
  elements.showTokens = document.getElementById('show-tokens');
  elements.tokenModel = document.getElementById('token-model');

  // 输出面板
  elements.commandOutput = document.getElementById('command-output');
  elements.copyBtn = document.getElementById('copy-btn');
  elements.validationArea = document.getElementById('validation-area');

  // 预设
  elements.presetChips = document.querySelectorAll('.preset-chip');
  elements.presetSelect = document.getElementById('preset-select');
  elements.loadPresetBtn = document.getElementById('load-preset-btn');
  elements.deletePresetBtn = document.getElementById('delete-preset-btn');
  elements.presetName = document.getElementById('preset-name');
  elements.savePresetBtn = document.getElementById('save-preset-btn');
  elements.exportConfigBtn = document.getElementById('export-config-btn');
  elements.importConfigBtn = document.getElementById('import-config-btn');
  elements.importFile = document.getElementById('import-file');

  // 卡片折叠
  elements.collapseBtns = document.querySelectorAll('.collapse-btn');

  // LLM 组
  elements.llmCard = document.getElementById('group-llm');

  // 运行控制
  elements.runBtn = document.getElementById('run-btn');
  elements.stopBtn = document.getElementById('stop-btn');
  elements.runStatus = document.getElementById('run-status');
  elements.statusDot = elements.runStatus.querySelector('.status-dot');
  elements.statusText = elements.runStatus.querySelector('.status-text');

  // 结果终端
  elements.resultTerminal = document.getElementById('result-terminal');
  elements.progressContainer = document.getElementById('progress-container');
  elements.progressFill = document.getElementById('progress-fill');
  elements.progressText = document.getElementById('progress-text');
  elements.outputContent = document.getElementById('output-content');
  elements.clearResultBtn = document.getElementById('clear-result-btn');
  elements.copyResultBtn = document.getElementById('copy-result-btn');
  elements.downloadResultBtn = document.getElementById('download-result-btn');
}

// ============================================
// 事件绑定
// ============================================
function bindEvents() {
  // 路径输入
  elements.path.addEventListener('input', () => {
    state.path = elements.path.value || '.';
    updateCommand();
  });

  // 输出文件
  elements.output.addEventListener('input', () => {
    state.output = elements.output.value;
    updateCommand();
  });

  // 排除模式
  elements.addExcludeBtn.addEventListener('click', addExcludePattern);
  elements.excludeInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addExcludePattern();
    }
  });

  // 开关
  elements.copy.addEventListener('change', () => {
    state.copy = elements.copy.checked;
    updateCommand();
  });

  elements.noSummary.addEventListener('change', () => {
    state.noSummary = elements.noSummary.checked;
    handleDependencies();
    updateCommand();
  });

  elements.interactive.addEventListener('change', () => {
    state.interactive = elements.interactive.checked;
    updateCommand();
  });

  // 日志控制 - 互斥逻辑
  elements.verboseRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      state.verbose = parseInt(radio.value);
      if (state.verbose > 0) {
        state.logLevel = '';
        elements.logLevel.value = '';
      }
      updateCommand();
    });
  });

  elements.logLevel.addEventListener('change', () => {
    state.logLevel = elements.logLevel.value;
    if (state.logLevel) {
      state.verbose = 0;
      elements.verboseRadios[0].checked = true;
    }
    updateCommand();
  });

  // LLM 选项
  elements.model.addEventListener('input', () => {
    state.model = elements.model.value;
    updateCommand();
  });

  elements.apiKey.addEventListener('input', () => {
    state.apiKey = elements.apiKey.value;
    updateCommand();
  });

  elements.toggleApiKey.addEventListener('click', () => {
    const type = elements.apiKey.type === 'password' ? 'text' : 'password';
    elements.apiKey.type = type;
    elements.toggleApiKey.textContent = type === 'password' ? '👁️' : '🙈';
  });

  elements.baseUrl.addEventListener('input', () => {
    state.baseUrl = elements.baseUrl.value;
    updateCommand();
  });

  elements.temperature.addEventListener('input', () => {
    state.temperature = parseFloat(elements.temperature.value);
    elements.temperatureValue.textContent = state.temperature.toFixed(1);
    updateCommand();
  });

  elements.maxWorkers.addEventListener('input', () => {
    state.maxWorkers = parseInt(elements.maxWorkers.value) || 5;
    updateCommand();
  });

  // 输出控制
  elements.maxLines.addEventListener('input', () => {
    const val = parseInt(elements.maxLines.value);
    state.maxLines = isNaN(val) ? null : val;
    updateCommand();
  });

  elements.outlineOnly.addEventListener('change', () => {
    state.outlineOnly = elements.outlineOnly.checked;
    updateCommand();
  });

  elements.outlineThreshold.addEventListener('input', () => {
    const val = parseInt(elements.outlineThreshold.value);
    state.outlineThreshold = isNaN(val) ? null : val;
    updateCommand();
  });

  // Token 预估
  elements.showTokens.addEventListener('change', () => {
    state.showTokens = elements.showTokens.checked;
    handleDependencies();
    updateCommand();
  });

  elements.tokenModel.addEventListener('input', () => {
    state.tokenModel = elements.tokenModel.value;
    updateCommand();
  });

  // 复制命令按钮
  elements.copyBtn.addEventListener('click', copyCommand);

  // 预设系统
  elements.presetChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const presetId = chip.dataset.preset;
      applyPreset(BUILTIN_PRESETS[presetId]);
    });
  });

  elements.loadPresetBtn.addEventListener('click', loadCustomPreset);
  elements.deletePresetBtn.addEventListener('click', deleteCustomPreset);
  elements.savePresetBtn.addEventListener('click', saveCustomPreset);
  elements.exportConfigBtn.addEventListener('click', exportConfig);
  elements.importConfigBtn.addEventListener('click', () => elements.importFile.click());
  elements.importFile.addEventListener('change', importConfig);

  // 卡片折叠
  elements.collapseBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const card = e.target.closest('.config-card');
      card.classList.toggle('collapsed');
    });
  });

  // 卡片头部点击折叠
  document.querySelectorAll('.card-header').forEach(header => {
    header.addEventListener('click', (e) => {
      if (!e.target.closest('.collapse-btn')) {
        const card = header.closest('.config-card');
        card.classList.toggle('collapsed');
      }
    });
  });

  // 运行控制
  elements.runBtn.addEventListener('click', startRun);
  elements.stopBtn.addEventListener('click', stopRun);
  elements.clearResultBtn.addEventListener('click', clearResultContent);
  elements.copyResultBtn.addEventListener('click', copyResult);
  elements.downloadResultBtn.addEventListener('click', downloadResult);
}

// ============================================
// 排除模式管理
// ============================================
function addExcludePattern() {
  const pattern = elements.excludeInput.value.trim();
  if (!pattern) return;

  if (state.exclude.includes(pattern)) {
    showToast('该模式已存在', 'warning');
    return;
  }

  state.exclude.push(pattern);
  elements.excludeInput.value = '';
  renderExcludeTags();
  updateCommand();
}

function removeExcludePattern(pattern) {
  state.exclude = state.exclude.filter(p => p !== pattern);
  renderExcludeTags();
  updateCommand();
}

function renderExcludeTags() {
  elements.excludeTags.innerHTML = state.exclude.map(pattern => `
    <span class="exclude-tag">
      ${escapeHtml(pattern)}
      <button onclick="removeExcludePattern('${escapeHtml(pattern)}')" aria-label="移除">×</button>
    </span>
  `).join('');
}

// ============================================
// 依赖处理
// ============================================
function handleDependencies() {
  // no-summary 禁用 LLM 组
  if (state.noSummary) {
    elements.llmCard.classList.add('disabled');
    disableLLMInputs(true);
  } else {
    elements.llmCard.classList.remove('disabled');
    disableLLMInputs(false);
  }

  // show-tokens 禁用 token-model
  elements.tokenModel.disabled = !state.showTokens;
}

function disableLLMInputs(disabled) {
  elements.model.disabled = disabled;
  elements.apiKey.disabled = disabled;
  elements.toggleApiKey.disabled = disabled;
  elements.baseUrl.disabled = disabled;
  elements.temperature.disabled = disabled;
  elements.maxWorkers.disabled = disabled;
}

// ============================================
// 命令生成
// ============================================
function generateCommand() {
  const parts = ['python -m repo2prompt.cli'];

  // 路径（总是第一个）
  if (state.path && state.path !== '.') {
    parts.push(escapeArg(state.path));
  }

  // 输出文件
  if (state.output) {
    parts.push('-o');
    parts.push(escapeArg(state.output));
  }

  // 排除模式
  state.exclude.forEach(pattern => {
    parts.push('-e');
    parts.push(escapeArg(pattern));
  });

  // 布尔标志
  if (state.copy) parts.push('-c');
  if (state.noSummary) parts.push('--no-summary');
  if (state.interactive) parts.push('-i');

  // 日志控制
  if (state.verbose === 1) {
    parts.push('-v');
  } else if (state.verbose === 2) {
    parts.push('-vv');
  } else if (state.logLevel) {
    parts.push('--log-level');
    parts.push(state.logLevel);
  }

  // LLM 选项（仅在非 no-summary 模式下）
  if (!state.noSummary) {
    if (state.model) {
      parts.push('--model');
      parts.push(state.model);
    }
    if (state.apiKey) {
      parts.push('--api-key');
      parts.push(escapeArg(state.apiKey));
    }
    if (state.baseUrl) {
      parts.push('--base-url');
      parts.push(escapeArg(state.baseUrl));
    }
    if (state.temperature !== 0.3) {
      parts.push('--temperature');
      parts.push(state.temperature.toString());
    }
    if (state.maxWorkers !== 5) {
      parts.push('--max-workers');
      parts.push(state.maxWorkers.toString());
    }
  }

  // 输出控制
  if (state.maxLines !== null) {
    parts.push('--max-lines');
    parts.push(state.maxLines.toString());
  }
  if (state.outlineOnly) parts.push('--outline-only');
  if (state.outlineThreshold !== null) {
    parts.push('--outline-threshold');
    parts.push(state.outlineThreshold.toString());
  }

  // Token 预估
  if (state.showTokens) {
    parts.push('--show-tokens');
    if (state.tokenModel) {
      parts.push('--token-model');
      parts.push(state.tokenModel);
    }
  }

  return parts;
}

function escapeArg(arg) {
  // 如果包含空格或特殊字符，用引号包裹
  if (/[\s"'`$\\]/.test(arg)) {
    return `"${arg.replace(/"/g, '\\"')}"`;
  }
  return arg;
}

function formatCommand(parts) {
  if (parts.length <= 4) {
    return parts.join(' ');
  }

  // 智能换行
  let lines = [parts[0]]; // python -m repo2prompt.cli
  let currentLine = '';

  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    const isFlag = part.startsWith('-');

    if (isFlag && currentLine.length > 0) {
      lines.push(currentLine);
      currentLine = '  ' + part;
    } else {
      currentLine += (currentLine ? ' ' : '  ') + part;
    }
  }

  if (currentLine) {
    lines.push(currentLine);
  }

  return lines.join(' \\\n');
}

function syntaxHighlight(command) {
  // 使用 DOM 操作实现语法高亮，避免正则替换破坏 HTML 结构
  const fragment = document.createDocumentFragment();
  const lines = command.split('\n');

  lines.forEach((line, lineIndex) => {
    if (lineIndex > 0) {
      fragment.appendChild(document.createTextNode('\n'));
    }

    // 处理续行符
    if (line.endsWith('\\')) {
      line = line.slice(0, -1);
    }

    // 分词
    const tokens = tokenize(line);
    tokens.forEach(token => {
      const span = document.createElement('span');
      span.className = token.type;
      span.textContent = token.value;
      fragment.appendChild(span);
    });

    // 添加续行符
    if (lines[lineIndex]?.endsWith('\\')) {
      const contSpan = document.createElement('span');
      contSpan.className = 'token-continuation';
      contSpan.textContent = '\\';
      fragment.appendChild(contSpan);
    }
  });

  return fragment;
}

function tokenize(line) {
  const tokens = [];
  let remaining = line;

  while (remaining.length > 0) {
    // 匹配可执行文件部分
    const execMatch = remaining.match(/^(python -m repo2prompt\.cli)/);
    if (execMatch) {
      tokens.push({ type: 'token-executable', value: execMatch[1] });
      remaining = remaining.slice(execMatch[1].length);
      continue;
    }

    // 匹配标志（--xxx 或 -x）
    const flagMatch = remaining.match(/^(\s*)(--?[\w-]+)/);
    if (flagMatch) {
      if (flagMatch[1]) tokens.push({ type: 'token-text', value: flagMatch[1] });
      tokens.push({ type: 'token-flag', value: flagMatch[2] });
      remaining = remaining.slice(flagMatch[0].length);
      continue;
    }

    // 匹配引号字符串
    const stringMatch = remaining.match(/^("(?:[^"\\]|\\.)*")/);
    if (stringMatch) {
      tokens.push({ type: 'token-string', value: stringMatch[1] });
      remaining = remaining.slice(stringMatch[1].length);
      continue;
    }

    // 匹配普通文本
    const textMatch = remaining.match(/^(\s+|[^\s-"]+)/);
    if (textMatch) {
      tokens.push({ type: 'token-text', value: textMatch[1] });
      remaining = remaining.slice(textMatch[1].length);
      continue;
    }

    // 单个字符
    tokens.push({ type: 'token-text', value: remaining[0] });
    remaining = remaining.slice(1);
  }

  return tokens;
}

// ============================================
// 验证
// ============================================
function validate() {
  const messages = [];

  // 路径验证
  if (!state.path) {
    messages.push({
      type: 'error',
      message: '项目路径不能为空'
    });
  }

  // API Key 验证（仅在摘要模式下）
  if (!state.noSummary && !state.apiKey) {
    messages.push({
      type: 'warning',
      message: '摘要模式下建议设置 API Key（也可通过环境变量 OPENAI_API_KEY 设置）'
    });
  }

  // 温度范围验证
  if (state.temperature < 0 || state.temperature > 2) {
    messages.push({
      type: 'error',
      message: '生成温度必须在 0-2 之间'
    });
  }

  // 并发数验证
  if (state.maxWorkers < 1 || state.maxWorkers > 50) {
    messages.push({
      type: 'error',
      message: '并发数必须在 1-50 之间'
    });
  }

  return messages;
}

function renderValidation(messages) {
  if (messages.length === 0) {
    elements.validationArea.innerHTML = '';
    return;
  }

  elements.validationArea.innerHTML = messages.map(msg => `
    <div class="validation-message ${msg.type}">
      <span class="validation-icon">${msg.type === 'error' ? '❌' : '⚠️'}</span>
      <span>${msg.message}</span>
    </div>
  `).join('');
}

// ============================================
// 更新命令和 UI
// ============================================
function updateCommand() {
  const parts = generateCommand();
  const command = formatCommand(parts);
  const highlighted = syntaxHighlight(command);

  // 清空并添加高亮后的内容
  elements.commandOutput.textContent = '';
  elements.commandOutput.appendChild(highlighted);

  const messages = validate();
  renderValidation(messages);

  // 自动保存状态
  saveStateToStorage();
}

// ============================================
// 复制命令
// ============================================
async function copyCommand() {
  const parts = generateCommand();
  const command = parts.join(' ');

  try {
    await navigator.clipboard.writeText(command);
    elements.copyBtn.classList.add('copied');
    elements.copyBtn.innerHTML = '<span class="btn-icon-copy">✓</span> 已复制';

    setTimeout(() => {
      elements.copyBtn.classList.remove('copied');
      elements.copyBtn.innerHTML = '<span class="btn-icon-copy">📋</span> 复制命令';
    }, 2000);

    showToast('命令已复制到剪贴板', 'success');
  } catch (err) {
    showToast('复制失败，请手动复制', 'error');
  }
}

// ============================================
// 预设系统
// ============================================
function applyPreset(preset) {
  // 重置状态
  resetState();

  // 应用预设状态
  Object.assign(state, preset.state);

  // 更新 UI
  applyStateToUI();
  handleDependencies();
  updateCommand();

  showToast(`已应用预设: ${preset.name}`, 'success');
}

function resetState() {
  state.path = '.';
  state.output = '';
  state.exclude = [];
  state.copy = false;
  state.noSummary = false;
  state.interactive = false;
  state.verbose = 0;
  state.logLevel = '';
  state.model = '';
  state.apiKey = '';
  state.baseUrl = '';
  state.temperature = 0.3;
  state.maxWorkers = 5;
  state.maxLines = null;
  state.outlineOnly = false;
  state.outlineThreshold = null;
  state.showTokens = false;
  state.tokenModel = '';
}

function applyStateToUI() {
  // 路径
  elements.path.value = state.path;

  // 通用选项
  elements.output.value = state.output;
  renderExcludeTags();
  elements.copy.checked = state.copy;
  elements.noSummary.checked = state.noSummary;
  elements.interactive.checked = state.interactive;

  // 日志控制
  elements.verboseRadios.forEach(radio => {
    radio.checked = parseInt(radio.value) === state.verbose;
  });
  elements.logLevel.value = state.logLevel;

  // LLM 选项
  elements.model.value = state.model;
  elements.apiKey.value = state.apiKey;
  elements.baseUrl.value = state.baseUrl;
  elements.temperature.value = state.temperature;
  elements.temperatureValue.textContent = state.temperature.toFixed(1);
  elements.maxWorkers.value = state.maxWorkers;

  // 输出控制
  elements.maxLines.value = state.maxLines || '';
  elements.outlineOnly.checked = state.outlineOnly;
  elements.outlineThreshold.value = state.outlineThreshold || '';

  // Token 预估
  elements.showTokens.checked = state.showTokens;
  elements.tokenModel.value = state.tokenModel;
}

// 自定义预设
function saveCustomPreset() {
  const name = elements.presetName.value.trim();
  if (!name) {
    showToast('请输入预设名称', 'warning');
    return;
  }

  const presets = getCustomPresets();
  presets[name] = { ...state };
  localStorage.setItem('repo2prompt_presets', JSON.stringify(presets));

  elements.presetName.value = '';
  updatePresetSelect();
  showToast(`预设 "${name}" 已保存`, 'success');
}

function loadCustomPreset() {
  const name = elements.presetSelect.value;
  if (!name) {
    showToast('请选择一个预设', 'warning');
    return;
  }

  const presets = getCustomPresets();
  if (presets[name]) {
    resetState();
    Object.assign(state, presets[name]);
    applyStateToUI();
    handleDependencies();
    updateCommand();
    showToast(`已加载预设: ${name}`, 'success');
  }
}

function deleteCustomPreset() {
  const name = elements.presetSelect.value;
  if (!name) {
    showToast('请选择要删除的预设', 'warning');
    return;
  }

  const presets = getCustomPresets();
  delete presets[name];
  localStorage.setItem('repo2prompt_presets', JSON.stringify(presets));

  updatePresetSelect();
  showToast(`预设 "${name}" 已删除`, 'success');
}

function getCustomPresets() {
  try {
    return JSON.parse(localStorage.getItem('repo2prompt_presets') || '{}');
  } catch {
    return {};
  }
}

function updatePresetSelect() {
  const presets = getCustomPresets();
  const options = ['<option value="">选择自定义预设...</option>'];

  Object.keys(presets).forEach(name => {
    options.push(`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`);
  });

  elements.presetSelect.innerHTML = options.join('');
}

// 导出/导入配置
function exportConfig() {
  const config = { ...state, _version: '1.0' };
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = 'repo2prompt-config.json';
  a.click();

  URL.revokeObjectURL(url);
  showToast('配置已导出', 'success');
}

function importConfig(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    try {
      const config = JSON.parse(event.target.result);
      delete config._version;

      resetState();
      Object.assign(state, config);
      applyStateToUI();
      handleDependencies();
      updateCommand();

      showToast('配置已导入', 'success');
    } catch (err) {
      showToast('导入失败：无效的 JSON 文件', 'error');
    }
  };
  reader.readAsText(file);

  // 重置文件输入
  e.target.value = '';
}

// ============================================
// 状态持久化
// ============================================
function saveStateToStorage() {
  try {
    localStorage.setItem('repo2prompt_state', JSON.stringify(state));
  } catch (e) {
    // 静默失败
  }
}

function loadSavedState() {
  try {
    const saved = localStorage.getItem('repo2prompt_state');
    if (saved) {
      const parsed = JSON.parse(saved);
      Object.assign(state, parsed);
    }
  } catch (e) {
    // 静默失败
  }

  updatePresetSelect();
}

// ============================================
// Toast 通知
// ============================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);

  // 自动移除
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// ============================================
// 工具函数
// ============================================
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================================
// 运行控制
// ============================================
let currentRunId = null;
let eventSource = null;
let lastOutput = '';

function collectRunParams() {
  return {
    path: state.path,
    output: state.output || null,
    exclude: state.exclude,
    copy: false, // Web 模式下不复制到剪贴板
    no_summary: state.noSummary,
    interactive: state.interactive,
    verbose: state.verbose,
    log_level: state.logLevel || null,
    model: state.model || null,
    api_key: state.apiKey || null,
    base_url: state.baseUrl || null,
    temperature: state.temperature,
    max_workers: state.maxWorkers,
    max_lines: state.maxLines,
    outline_only: state.outlineOnly,
    outline_threshold: state.outlineThreshold,
    show_tokens: state.showTokens,
    token_model: state.tokenModel || null,
  };
}

async function startRun() {
  const params = collectRunParams();

  // 验证
  if (!params.path) {
    showToast('项目路径不能为空', 'error');
    return;
  }

  if (!params.no_summary && !params.api_key) {
    showToast('摘要模式需要 API Key', 'error');
    return;
  }

  // 更新 UI 状态
  setRunStatus('running');
  clearResult();
  lastOutput = '';

  try {
    // 发起运行请求
    const response = await fetch(`${API_BASE}/api/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start run');
    }

    const { run_id } = await response.json();
    currentRunId = run_id;

    // 建立 SSE 连接
    eventSource = new EventSource(`${API_BASE}/api/stream/${run_id}`);

    eventSource.addEventListener('log', (e) => {
      const data = JSON.parse(e.data);
      appendLogLine(data.level, data.msg);
    });

    eventSource.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      updateProgress(data.current, data.total, data.file);
    });

    eventSource.addEventListener('output', (e) => {
      const data = JSON.parse(e.data);
      lastOutput = data.content;
      renderOutput(data.content);
    });

    eventSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      setRunStatus('complete', data);
      enableResultActions();
      eventSource.close();
      eventSource = null;
    });

    eventSource.addEventListener('error', (e) => {
      if (e.data) {
        const data = JSON.parse(e.data);
        appendLogLine('error', data.msg);
      }
      setRunStatus('error');
      eventSource.close();
      eventSource = null;
    });

    // SSE 连接错误处理
    eventSource.onerror = () => {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      if (currentRunId) {
        setRunStatus('error');
        appendLogLine('error', '连接断开');
      }
    };

  } catch (err) {
    setRunStatus('error');
    appendLogLine('error', err.message);
  }
}

async function stopRun() {
  if (currentRunId) {
    try {
      await fetch(`${API_BASE}/api/cancel/${currentRunId}`, { method: 'POST' });
    } catch (e) {
      // 忽略错误
    }
  }

  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  currentRunId = null;
  setRunStatus('idle');
  appendLogLine('warning', '已取消运行');
}

function setRunStatus(status, data = null) {
  const dot = elements.statusDot;
  const text = elements.statusText;
  const runBtn = elements.runBtn;
  const stopBtn = elements.stopBtn;

  // 移除所有状态类
  dot.className = 'status-dot';

  switch (status) {
    case 'idle':
      dot.classList.add('idle');
      text.textContent = '就绪';
      runBtn.style.display = '';
      runBtn.disabled = false;
      stopBtn.style.display = 'none';
      break;

    case 'running':
      dot.classList.add('running');
      text.textContent = '运行中...';
      runBtn.style.display = 'none';
      stopBtn.style.display = '';
      break;

    case 'complete':
      dot.classList.add('complete');
      const elapsed = data ? `${data.elapsed}s` : '';
      const bytes = data ? formatBytes(data.bytes) : '';
      text.textContent = `完成 ${elapsed} ${bytes}`;
      runBtn.style.display = '';
      runBtn.disabled = false;
      stopBtn.style.display = 'none';
      currentRunId = null;
      break;

    case 'error':
      dot.classList.add('error');
      text.textContent = '出错';
      runBtn.style.display = '';
      runBtn.disabled = false;
      stopBtn.style.display = 'none';
      currentRunId = null;
      break;
  }
}

function clearResult() {
  elements.outputContent.innerHTML = '';
  elements.progressContainer.style.display = 'none';
  elements.progressFill.style.width = '0%';
  elements.progressText.textContent = '0/0';
  elements.copyResultBtn.disabled = true;
  elements.downloadResultBtn.disabled = true;
}

function clearResultContent() {
  clearResult();
  lastOutput = '';
  elements.outputContent.innerHTML = '<span class="result-placeholder">点击"运行"按钮执行命令...</span>';
}

function appendLogLine(level, msg) {
  const line = document.createElement('div');
  line.className = `log-line ${level}`;
  line.textContent = msg;
  elements.outputContent.appendChild(line);
  scrollToBottom();
}

function updateProgress(current, total, file) {
  elements.progressContainer.style.display = 'flex';
  const percent = total > 0 ? (current / total * 100) : 0;
  elements.progressFill.style.width = `${percent}%`;
  elements.progressText.textContent = `${current}/${total}`;
}

function renderOutput(content) {
  // 清空之前的内容，保留日志行
  const logLines = elements.outputContent.querySelectorAll('.log-line');
  elements.outputContent.innerHTML = '';
  logLines.forEach(line => elements.outputContent.appendChild(line));

  // 添加输出内容
  const outputPre = document.createElement('pre');
  outputPre.className = 'output-text';
  outputPre.textContent = content;
  elements.outputContent.appendChild(outputPre);
  scrollToBottom();
}

function scrollToBottom() {
  const body = document.getElementById('result-body');
  body.scrollTop = body.scrollHeight;
}

function enableResultActions() {
  elements.copyResultBtn.disabled = false;
  elements.downloadResultBtn.disabled = false;
}

async function copyResult() {
  if (!lastOutput) return;

  try {
    await navigator.clipboard.writeText(lastOutput);
    showToast('结果已复制到剪贴板', 'success');
  } catch (err) {
    showToast('复制失败', 'error');
  }
}

function downloadResult() {
  if (!lastOutput) return;

  const blob = new Blob([lastOutput], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'repo2prompt-output.txt';
  a.click();
  URL.revokeObjectURL(url);
  showToast('文件已下载', 'success');
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ============================================
// 启动应用
// ============================================
document.addEventListener('DOMContentLoaded', initApp);
