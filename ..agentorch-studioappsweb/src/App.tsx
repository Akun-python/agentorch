import './App.css'

type IconName = 'orchestration' | 'agents' | 'tools' | 'memory' | 'knowledge' | 'workflow'

const capabilities: { icon: IconName; title: string; text: string; tone: string }[] = [
  { icon: 'orchestration', title: '运行时编排', text: '把路由、委派、交接和聚合变成可追踪的显式对象。', tone: 'coral' },
  { icon: 'agents', title: '多智能体协作', text: '从单智能体平滑扩展到多角色协同，边界清晰可控。', tone: 'violet' },
  { icon: 'tools', title: '工具与沙箱', text: '按策略控制工具可见性、执行权限和安全边界。', tone: 'amber' },
  { icon: 'memory', title: '记忆治理', text: '跨轮状态、长期记忆和持久化记录可管理、可审计。', tone: 'blue' },
  { icon: 'knowledge', title: '知识与 RAG', text: '保留检索证据链，让生成结果更容易复核和解释。', tone: 'teal' },
  { icon: 'workflow', title: '工作流 DAG', text: '把复杂任务拆成可组合、可重试、可观测的执行节点。', tone: 'pink' },
]

const stack = [
  ['Python', '核心语言', '#3b82f6'], ['AsyncIO', '异步运行时', '#8b5cf6'], ['Pydantic', '类型与校验', '#10b981'],
  ['OpenAI API', '模型适配', '#111827'], ['Jinja2', '提示词模板', '#f97316'], ['Neo4j', '图存储扩展', '#0ea5e9'],
]

const projects = [
  { icon: '/brand/project-memory-graph.svg', name: 'Long-term Memory Graph', tag: 'Research', text: '长程记忆、图结构与基线对比实验。' },
  { icon: '/brand/project-ai-for-detect.svg', name: 'AI for Detect', tag: 'Application', text: '面向行业文本的检测与结构化处理。' },
  { icon: '/brand/project-ai-short-drama.svg', name: 'AI Short Drama', tag: 'Application', text: '多智能体短剧生产与视频工作流。' },
]

function SymbolIcon({ name }: { name: IconName }) {
  return <svg className="symbol-icon" aria-hidden="true"><use href={`/icons.svg#${name}`} /></svg>
}

function App() {
  return (
    <main>
      <nav className="nav shell">
        <a className="brand" href="#top" aria-label="agentorch 首页"><img src="/brand/agentorch-mark.svg" alt="" /><span>agentorch</span></a>
        <div className="nav-links"><a href="#architecture">架构</a><a href="#stack">技术栈</a><a href="#projects">项目</a><a href="https://github.com/Akun-python/agentorch" target="_blank" rel="noreferrer">GitHub ↗</a></div>
      </nav>

      <section className="hero shell" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span className="pulse" /> CODE-FIRST · ASYNC-FIRST</div>
          <h1>让智能体协作<br /><em>成为可编排的工程。</em></h1>
          <p className="hero-lead">agentorch 是一个面向真实工程边界的 Python 多智能体编排框架。把工具、记忆、知识、工作流与模型，组合成清晰、可观测、可演进的运行时。</p>
          <div className="hero-actions"><a className="button primary" href="https://github.com/Akun-python/agentorch" target="_blank" rel="noreferrer">查看 GitHub <span>↗</span></a><a className="button secondary" href="#architecture">了解架构 <span>↓</span></a></div>
          <div className="hero-meta"><span><strong>3</strong> 核心入口</span><span><strong>7</strong> 能力模块</span><span><strong>3.10+</strong> Python</span></div>
        </div>
        <div className="hero-art" aria-label="agentorch 编排网络示意图">
          <div className="art-glow" /><div className="orbit orbit-a" /><div className="orbit orbit-b" /><div className="art-line line-a" /><div className="art-line line-b" /><div className="art-line line-c" />
          <div className="art-node node-a"><SymbolIcon name="agents" /><small>AGENTS</small></div><div className="art-node node-b"><SymbolIcon name="tools" /><small>TOOLS</small></div><div className="art-node node-c"><SymbolIcon name="memory" /><small>MEMORY</small></div>
          <div className="core-mark"><img src="/brand/agentorch-mark.svg" alt="agentorch" /><span>ORCHESTRATOR</span></div>
        </div>
      </section>

      <section className="architecture shell" id="architecture">
        <div className="section-heading"><div><span className="kicker">01 / ARCHITECTURE</span><h2>一套运行时，<br /><span>连接所有能力。</span></h2></div><p>从请求进入，到模型响应、工具执行和多智能体委派，每一步都拥有明确边界和结构化状态。</p></div>
        <div className="capability-grid">{capabilities.map((item) => <article className="capability-card" key={item.title}><div className={`card-icon ${item.tone}`}><SymbolIcon name={item.icon} /></div><h3>{item.title}</h3><p>{item.text}</p><span className="card-arrow">↗</span></article>)}</div>
      </section>

      <section className="stack-section" id="stack"><div className="shell"><div className="section-heading compact"><div><span className="kicker">02 / STACK</span><h2>少而稳的技术底座。</h2></div><p>轻量核心依赖，开放扩展接口，保持从原型到生产的迁移路径。</p></div><div className="stack-grid">{stack.map(([name, role, color]) => <div className="stack-item" key={name}><span className="stack-logo" style={{ background: color }}>{name.slice(0, 1)}</span><div><strong>{name}</strong><small>{role}</small></div></div>)}</div></div></section>

      <section className="projects shell" id="projects"><div className="section-heading compact"><div><span className="kicker">03 / BUILT WITH AGENTORCH</span><h2>从框架，到真实项目。</h2></div><p>用统一的编排能力承载研究实验和应用落地。</p></div><div className="project-grid">{projects.map((project) => <article className="project-card" key={project.name}><img src={project.icon} alt="" /><div><span className="project-tag">{project.tag}</span><h3>{project.name}</h3><p>{project.text}</p><a href="https://github.com/Akun-python/agentorch" target="_blank" rel="noreferrer">探索项目 ↗</a></div></article>)}</div></section>

      <footer className="footer shell"><a className="brand" href="#top"><img src="/brand/agentorch-mark.svg" alt="" /><span>agentorch</span></a><p>Build systems that think together.</p><span className="footer-note">MIT · Python 3.10+</span></footer>
    </main>
  )
}

export default App
