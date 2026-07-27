import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BadgeCheck,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Clock3,
  Download,
  FileUp,
  FileText,
  Globe2,
  LayoutDashboard,
  ListChecks,
  LockKeyhole,
  LoaderCircle,
  Network,
  Presentation,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  WandSparkles,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

const sampleRequirement = `Customer needs a secure internal AI assistant that can answer questions from company documents, enforce role-based access control, integrate with enterprise identity, and support thousands of users. The solution should preserve audit logs, protect confidential documents, and provide proposal content that can be exported to enterprise PowerPoint templates.`;

const REQUIREMENT_LABELS = {
  business_goals: 'Business goals',
  functional_requirements: 'Functional requirements',
  non_functional_requirements: 'Quality and scale',
  constraints: 'Constraints',
  assumptions: 'Assumptions',
  integrations: 'Integrations',
  security_needs: 'Security needs',
  expected_users: 'Expected users',
};

const WORKBENCH_NAVIGATION = [
  { id: 'workspace', label: 'Workspace', caption: 'Input and runtime', icon: LayoutDashboard },
  { id: 'requirements', label: 'Requirements', caption: 'Traceable extraction', icon: ListChecks },
  { id: 'architecture', label: 'Architecture', caption: 'Research and approval', icon: Network },
  { id: 'proposal', label: 'Proposal', caption: 'Draft and PPTX', icon: Presentation },
];

const initialCostAssumptions = {
  development: '',
  test: '',
  uat_or_staging: '',
};

const PRESENTATION_PIPELINES = [
  {
    id: 'starter_renderer',
    label: 'Starter renderer',
    caption: 'Deterministic local PPTX renderer',
  },
  {
    id: 'master_template',
    label: 'Master template fill',
    caption: 'Maps the proposal into the provided enterprise master.pptx deck',
  },
  {
    id: 'deep_presenter',
    label: 'DeepPresenter',
    caption: 'AgentLoop research + PPTAgent via local Docker runtime',
  },
];

const RESEARCH_MODE_LABELS = {
  azure_official_only: 'Azure official',
  azure_github_papers: 'Azure + GitHub + papers',
  off: 'No web research',
};

const NO_ADDITIONAL_INFORMATION = 'No additional information provided. Proceed with a solution architect assumption and validate it before implementation.';
const extractionRuntimeLabel = (mode) => mode === 'foundry_published_requirement_agent'
  ? 'Published Requirement Agent'
  : mode === 'failed' || mode === 'unavailable'
    ? 'Requirement Agent unavailable'
    : 'Unexpected legacy runtime';

const Card = ({ className = '', children }) => (
  <section className={`rounded-lg border border-slate-700 bg-slate-900/70 ${className}`}>{children}</section>
);

const StatusPill = ({ tone = 'neutral', children }) => {
  const tones = {
    neutral: 'border-slate-600 bg-slate-800 text-slate-300',
    running: 'border-cyan-500/50 bg-cyan-500/10 text-cyan-100',
    ready: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
    warning: 'border-amber-500/40 bg-amber-500/10 text-amber-100',
  };
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
};

const SolutionArchitectProposalPage = () => {
  const [documentText, setDocumentText] = useState(sampleRequirement);
  const [analysis, setAnalysis] = useState(null);
  const [clarifications, setClarifications] = useState({});
  const [research, setResearch] = useState(null);
  const [researchMode, setResearchMode] = useState('azure_official_only');
  const [privateReferences, setPrivateReferences] = useState([]);
  const [architectureApproved, setArchitectureApproved] = useState(false);
  const [costAssumptions, setCostAssumptions] = useState(initialCostAssumptions);
  const [proposal, setProposal] = useState(null);
  const [templateId, setTemplateId] = useState('starter');
  const [presentationPipeline, setPresentationPipeline] = useState('starter_renderer');
  const [activeOperation, setActiveOperation] = useState('');
  const [operationStartedAt, setOperationStartedAt] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isUploadingReference, setIsUploadingReference] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [error, setError] = useState('');
  const [expandedCategory, setExpandedCategory] = useState('functional_requirements');
  const [showRawArchitecture, setShowRawArchitecture] = useState(false);
  const [activeView, setActiveView] = useState('workspace');
  const [hitlDialog, setHitlDialog] = useState('');
  const [hitlThreadId, setHitlThreadId] = useState('');
  const [architectureFeedback, setArchitectureFeedback] = useState('');
  const [useExternalEvidence, setUseExternalEvidence] = useState(false);

  useEffect(() => {
    if (presentationPipeline === 'master_template') {
      setTemplateId('master_template');
    }
  }, [presentationPipeline]);

  const isBusy = Boolean(activeOperation);
  const architecture = research?.architecture;
  const extracted = analysis?.extracted;
  const architectureSources = useMemo(
    () => architecture?.research_sources || research?.sources || [],
    [architecture, research],
  );
  const activeStage = WORKBENCH_NAVIGATION.findIndex((item) => item.id === activeView);
  const ocrPageCount = useMemo(() => {
    const parserPages = analysis?.ingestion?.stats?.parser_pages || {};
    return Object.entries(parserPages).reduce(
      (sum, [parser, count]) => sum + (String(parser).startsWith('document_intelligence') ? Number(count || 0) : 0),
      0,
    );
  }, [analysis]);

  useEffect(() => {
    if (!operationStartedAt) return undefined;
    const interval = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - operationStartedAt) / 1000));
    }, 500);
    return () => window.clearInterval(interval);
  }, [operationStartedAt]);

  useEffect(() => {
    const savedThreadId = window.localStorage.getItem('proposalHitlThreadId');
    if (!savedThreadId) return undefined;
    let active = true;
    fetch(`${API_BASE}/proposal/hitl/${savedThreadId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!active || !data?.state?.extraction) return;
        const restored = data.state;
        setHitlThreadId(savedThreadId);
        setAnalysis(restored.extraction);
        setClarifications(restored.clarifications || {});
        setResearchMode(restored.research_mode || 'azure_official_only');
        setUseExternalEvidence(restored.research_mode === 'azure_github_papers');
        setResearch(restored.research_result || null);
        setProposal(restored.proposal || null);
        setArchitectureApproved(restored.architecture_decision === 'approved');
        if (data.interrupt_payload?.type === 'requirement_review') setHitlDialog('requirements');
        if (data.interrupt_payload?.type === 'architecture_review') setHitlDialog('architecture');
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const beginOperation = (operation) => {
    setActiveOperation(operation);
    setOperationStartedAt(Date.now());
    setElapsedSeconds(0);
    setError('');
  };

  const finishOperation = () => {
    setActiveOperation('');
    setOperationStartedAt(null);
  };

  const canOpenWorkbenchView = (viewId) => {
    if (viewId === 'workspace') return true;
    if (viewId === 'requirements') return Boolean(analysis);
    if (viewId === 'architecture') return Boolean(analysis);
    if (viewId === 'proposal') return Boolean(architectureApproved || proposal);
    return false;
  };
  const sourceRecordByStatement = useMemo(() => {
    const records = {};
    Object.values(analysis?.traceability || {}).flat().forEach((record) => {
      records[record.statement] = record;
    });
    return records;
  }, [analysis]);

  const requirementCount = useMemo(
    () => Object.values(extracted || {}).reduce((sum, values) => sum + (Array.isArray(values) ? values.length : 0), 0),
    [extracted],
  );

  const operationLabel = {
    analyze: 'Extracting and validating requirements',
    research: researchMode === 'off' ? 'Generating architecture draft' : `Researching with ${RESEARCH_MODE_LABELS[researchMode] || 'approved sources'} and generating architecture`,
    generate: 'Writing the customer-ready proposal',
    export: 'Rendering the PowerPoint template',
  }[activeOperation];

  const analyzeText = async () => {
    beginOperation('analyze');
    setDownloadUrl('');
    setResearch(null);
    setProposal(null);
    try {
      const response = await fetch(`${API_BASE}/proposal/hitl/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_text: documentText, template_id: templateId, research_mode: researchMode }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Analyze failed');
      if (data.state?.status === 'failed') throw new Error(data.state.error || 'Requirement Agent failed');
      setAnalysis(data.state?.extraction || null);
      setHitlThreadId(data.thread_id || '');
      window.localStorage.setItem('proposalHitlThreadId', data.thread_id || '');
      setClarifications({});
      setPrivateReferences([]);
      setArchitectureApproved(false);
      setCostAssumptions(initialCostAssumptions);
      setActiveView('requirements');
      setHitlDialog('requirements');
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  const uploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    beginOperation('analyze');
    setDownloadUrl('');
    setResearch(null);
    setProposal(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      formData.append('template_id', templateId);
      formData.append('research_mode', researchMode);
      const response = await fetch(`${API_BASE}/proposal/hitl/start-upload`, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Upload failed');
      if (data.state?.status === 'failed') throw new Error(data.state.error || 'Requirement Agent failed');
      setAnalysis(data.state?.extraction || null);
      setHitlThreadId(data.thread_id || '');
      window.localStorage.setItem('proposalHitlThreadId', data.thread_id || '');
      setClarifications({});
      setPrivateReferences([]);
      setArchitectureApproved(false);
      setCostAssumptions(initialCostAssumptions);
      setActiveView('requirements');
      setHitlDialog('requirements');
    } catch (err) {
      setError(err.message);
    } finally {
      event.target.value = '';
      finishOperation();
    }
  };

  const uploadReferenceFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploadingReference(true);
    setError('');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch(`${API_BASE}/proposal/reference-upload`, { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Reference upload failed');
      setPrivateReferences((current) => [...current, data.reference]);
    } catch (err) {
      setError(err.message);
    } finally {
      event.target.value = '';
      setIsUploadingReference(false);
    }
  };

  const generateProposal = async () => {
    if (!extracted || !architecture || !architectureApproved) return;
    beginOperation('generate');
    try {
      const formattedCosts = Object.entries(costAssumptions)
        .filter(([, monthlyEstimateUsd]) => monthlyEstimateUsd.trim())
        .map(([environment, monthlyEstimateUsd]) => ({ environment, monthly_estimate_usd: monthlyEstimateUsd.trim() }));
      const response = await fetch(`${API_BASE}/proposal/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extracted,
          clarifications,
          architecture_decisions: architecture,
          cost_assumptions: formattedCosts,
          template_id: templateId,
          architecture_approved: architectureApproved,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Proposal generation failed');
      setProposal(data.proposal);
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  const exportPpt = async () => {
    if (!proposal) return;
    beginOperation('export');
    try {
      const response = await fetch(`${API_BASE}/proposal/export-pptx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal, template_id: templateId, presentation_pipeline: presentationPipeline }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Export failed');
      setDownloadUrl(data.download_url);
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  const continueFromRequirementHitl = async () => {
    if (!hitlThreadId) return;
    const completedClarifications = { ...clarifications };
    (analysis?.clarification_questions || []).forEach((item) => {
      if (!completedClarifications[item.field]?.trim()) {
        completedClarifications[item.field] = 'Not specified. Record a solution architect assumption and validate it before implementation.';
      }
    });
    if (!completedClarifications.hitl_review) {
      completedClarifications.hitl_review = NO_ADDITIONAL_INFORMATION;
    }
    let architectInstruction = completedClarifications.hitl_review === NO_ADDITIONAL_INFORMATION ? '' : completedClarifications.hitl_review;
    if (useExternalEvidence) {
      const evidenceInstruction = 'Use safe public web search with Azure official documentation, Microsoft/Azure GitHub repositories, and relevant public research papers to support architecture decisions. Do not send customer document text, customer names, private URLs, credentials, or internal identifiers to web search.';
      architectInstruction = architectInstruction ? `${architectInstruction}\n\n${evidenceInstruction}` : evidenceInstruction;
      completedClarifications.hitl_review = architectInstruction;
    }
    const selectedResearchMode = useExternalEvidence ? 'azure_github_papers' : researchMode;
    beginOperation('research');
    try {
      const response = await fetch(`${API_BASE}/proposal/hitl/${hitlThreadId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision: 'approved',
          clarifications: completedClarifications,
          additional_instruction: architectInstruction,
          research_mode: selectedResearchMode,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.state?.status === 'failed') throw new Error(data.state?.error || data.error || 'Architecture generation failed');
      const nextState = data.state || {};
      setAnalysis(nextState.extraction || analysis);
      setClarifications(nextState.clarifications || completedClarifications);
      setResearchMode(nextState.research_mode || selectedResearchMode);
      setResearch(nextState.research_result || null);
      setArchitectureApproved(false);
      setHitlDialog(data.interrupt_payload?.type === 'architecture_review' ? 'architecture' : '');
      setActiveView('architecture');
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  const approveArchitecture = async () => {
    if (!hitlThreadId) return;
    beginOperation('generate');
    try {
      const formattedCosts = Object.entries(costAssumptions)
        .filter(([, monthlyEstimateUsd]) => monthlyEstimateUsd.trim())
        .map(([environment, monthlyEstimateUsd]) => ({ environment, monthly_estimate_usd: monthlyEstimateUsd.trim() }));
      const response = await fetch(`${API_BASE}/proposal/hitl/${hitlThreadId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approved', cost_assumptions: formattedCosts }),
      });
      const data = await response.json();
      if (!response.ok || data.state?.status === 'failed') throw new Error(data.state?.error || data.error || 'Proposal generation failed');
      const nextState = data.state || {};
      setResearch(nextState.research_result || research);
      setProposal(nextState.proposal || null);
      setArchitectureApproved(nextState.architecture_decision === 'approved');
      setHitlDialog('');
      setActiveView('proposal');
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  const requestArchitectureChanges = async () => {
    if (!hitlThreadId || !architectureFeedback.trim()) {
      setError('Describe the required architecture change before sending it back to the Architect Agent.');
      return;
    }
    beginOperation('research');
    try {
      const response = await fetch(`${API_BASE}/proposal/hitl/${hitlThreadId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'changes_requested', feedback: architectureFeedback.trim() }),
      });
      const data = await response.json();
      if (!response.ok || data.state?.status === 'failed') throw new Error(data.state?.error || data.error || 'Architecture revision failed');
      setResearch(data.state?.research_result || null);
      setArchitectureFeedback('');
      setHitlDialog(data.interrupt_payload?.type === 'architecture_review' ? 'architecture' : '');
    } catch (err) {
      setError(err.message);
    } finally {
      finishOperation();
    }
  };

  return (
    <main className="min-h-full bg-slate-950 px-4 py-5 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-5 lg:flex-row lg:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-cyan-300">
              <Sparkles size={16} /> Solution architect workbench
            </div>
            <h1 className="text-2xl font-semibold tracking-normal text-white sm:text-3xl">Proposal generation</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              Turn a customer requirement into a traceable architecture decision and a template-ready proposal.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <ShieldCheck size={17} className="text-emerald-400" />
            Customer content stays out of public web queries
          </div>
        </header>

        <div className="flex items-start gap-5">
          <aside className="sticky top-4 hidden w-56 shrink-0 border-r border-slate-800 pr-4 lg:block">
            <div className="mb-3 px-2 text-xs font-semibold uppercase tracking-normal text-slate-500">Proposal workspace</div>
            <nav aria-label="Proposal workbench navigation" className="space-y-1">
              {WORKBENCH_NAVIGATION.map((item) => {
                const Icon = item.icon;
                const selected = activeView === item.id;
                const available = canOpenWorkbenchView(item.id);
                const count = item.id === 'requirements' ? requirementCount : null;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      if (available) setActiveView(item.id);
                    }}
                    disabled={!available}
                    title={available ? `Open ${item.label}` : 'Analyze requirements first to unlock this output'}
                    className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2.5 text-left transition ${selected ? 'bg-cyan-400/10 text-cyan-100' : available ? 'text-slate-400 hover:bg-slate-900 hover:text-slate-100' : 'cursor-not-allowed text-slate-700'}`}
                  >
                    {available ? <Icon size={17} className={selected ? 'text-cyan-300' : 'text-slate-500'} /> : <LockKeyhole size={16} className="text-slate-700" />}
                    <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{item.label}</span><span className="block truncate text-xs text-slate-500">{item.caption}</span></span>
                    {typeof count === 'number' && count > 0 ? <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300">{count}</span> : null}
                  </button>
                );
              })}
            </nav>
            <div className="mt-6 rounded-md border border-slate-800 bg-slate-900/50 p-3 text-xs leading-5 text-slate-400">
              <div className="mb-1 flex items-center gap-2 text-slate-200"><ShieldCheck size={14} className="text-emerald-400" /> Safe research policy</div>
              Public research uses safe technical queries only. Customer content is never sent to web search.
            </div>
          </aside>

          <div className="min-w-0 flex-1 space-y-5">
        <nav aria-label="Proposal mobile navigation" className="flex gap-1 overflow-x-auto border-b border-slate-800 pb-2 lg:hidden">
          {WORKBENCH_NAVIGATION.map((item) => {
            const Icon = item.icon;
            const selected = activeView === item.id;
            const available = canOpenWorkbenchView(item.id);
            return (
              <button key={item.id} type="button" onClick={() => available && setActiveView(item.id)} disabled={!available} className={`inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm ${selected ? 'bg-cyan-400/10 text-cyan-100' : available ? 'text-slate-400' : 'text-slate-700'}`}>
                {available ? <Icon size={15} /> : <LockKeyhole size={14} />} {item.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div><p className="text-xs font-medium uppercase tracking-normal text-slate-500">Stage {Math.max(activeStage, 0) + 1} of 4</p><p className="mt-1 text-sm font-medium text-slate-100">{WORKBENCH_NAVIGATION.find((item) => item.id === activeView)?.label}</p></div>
          {isBusy ? <StatusPill tone="running">Running {elapsedSeconds}s</StatusPill> : <StatusPill tone="ready">Ready</StatusPill>}
        </div>

        {isBusy && (
          <div className="flex items-center gap-3 rounded-md border border-cyan-400/20 bg-cyan-400/5 px-3 py-2 text-sm text-cyan-100">
            <LoaderCircle className="animate-spin" size={18} />
            <span>{operationLabel}</span>
            <span className="ml-auto text-xs text-cyan-200/70">Running {elapsedSeconds}s</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-3 rounded-md border border-red-500/40 bg-red-950/40 p-3 text-sm text-red-100">
            <CircleAlert className="mt-0.5 shrink-0" size={18} />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-5">
          <div className={`space-y-5 ${['workspace', 'requirements'].includes(activeView) ? '' : 'hidden'}`}>
            <Card className={activeView === 'workspace' ? '' : 'hidden'}>
              <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
                <div>
                  <h2 className="text-base font-semibold text-white">1. Customer requirement</h2>
                  <p className="mt-1 text-xs text-slate-400">Paste a requirement or upload a source document.</p>
                </div>
                <StatusPill tone={analysis ? 'ready' : 'neutral'}>{analysis ? `${requirementCount} requirements` : 'Awaiting input'}</StatusPill>
              </div>
              <div className="p-4">
                <textarea
                  className="h-64 w-full resize-y rounded-md border border-slate-700 bg-slate-950 p-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
                  value={documentText}
                  onChange={(event) => setDocumentText(event.target.value)}
                  disabled={isBusy}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" onClick={analyzeText} disabled={isBusy || !documentText.trim()} className="inline-flex items-center gap-2 rounded-md bg-cyan-500 px-3 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40">
                    {activeOperation === 'analyze' ? <LoaderCircle className="animate-spin" size={17} /> : <WandSparkles size={17} />}
                    Analyze requirement
                  </button>
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-500">
                    <UploadCloud size={17} /> Upload DOCX, PDF or TXT
                    <input className="hidden" type="file" accept=".docx,.pdf,.txt,.md" onChange={uploadFile} disabled={isBusy} />
                  </label>
                </div>
                {analysis?.ingestion?.stats && (
                  <div className="mt-4 grid grid-cols-2 divide-x divide-slate-800 rounded-md border border-slate-800 bg-slate-950/60 text-center sm:grid-cols-4">
                    <div className="p-2"><div className="text-lg font-semibold text-white">{analysis.ingestion.stats.pages || 1}</div><div className="text-xs text-slate-500">pages</div></div>
                    <div className="p-2"><div className="text-lg font-semibold text-white">{analysis.ingestion.stats.chunks || 0}</div><div className="text-xs text-slate-500">traceable chunks</div></div>
                    <div className="p-2"><div className="text-lg font-semibold text-white">{analysis.batch_count || 0}</div><div className="text-xs text-slate-500">agent batches</div></div>
                    <div className="p-2"><div className="text-lg font-semibold text-cyan-200">{ocrPageCount}</div><div className="text-xs text-slate-500">OCR pages</div></div>
                  </div>
                )}
              </div>
            </Card>

            <Card className={activeView === 'requirements' ? '' : 'hidden'}>
              <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
                <div>
                  <h2 className="text-base font-semibold text-white">2. Requirement review</h2>
                  <p className="mt-1 text-xs text-slate-400">Deduplicated requirements, grouped by one primary category.</p>
                </div>
                {analysis ? <div className="flex flex-wrap justify-end gap-2"><StatusPill tone={analysis.extraction_mode === 'foundry_published_requirement_agent' ? 'ready' : 'warning'}>{extractionRuntimeLabel(analysis.extraction_mode)}</StatusPill><StatusPill tone="ready">Traceability checked</StatusPill></div> : null}
              </div>
              <div className="p-4">
                {!extracted ? (
                  <p className="py-5 text-sm text-slate-500">Run the analysis to review extracted requirements.</p>
                ) : (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-400/20 bg-amber-400/5 px-3 py-2.5">
                      <p className="text-sm text-amber-100">Review the extracted output, then complete or update the human review before architecture.</p>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => setHitlDialog('requirements')} className="inline-flex items-center gap-2 rounded-md border border-amber-400/40 bg-slate-950 px-3 py-2 text-sm font-medium text-amber-100 hover:border-amber-300 hover:text-white"><CircleAlert size={16} /> Open HITL review</button>
                        <button type="button" onClick={() => setActiveView('architecture')} className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-sm font-medium text-white hover:bg-violet-400">Go to architecture <ArrowRight size={16} /></button>
                      </div>
                    </div>
                    {Object.entries(REQUIREMENT_LABELS).map(([category, label]) => {
                      const items = extracted[category] || [];
                      const expanded = expandedCategory === category;
                      return (
                        <div key={category} className="rounded-md border border-slate-800 bg-slate-950/45">
                          <button type="button" onClick={() => setExpandedCategory(expanded ? '' : category)} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
                            {expanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            <span className="flex-1 text-sm font-medium text-slate-200">{label}</span>
                            <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">{items.length}</span>
                          </button>
                          {expanded && (
                            <div className="space-y-2 border-t border-slate-800 p-3">
                              {items.length ? items.map((statement, index) => {
                                const trace = sourceRecordByStatement[statement];
                                return (
                                  <article key={`${category}-${index}`} className="rounded-md border border-slate-800 bg-slate-900/70 p-3">
                                    <p className="text-sm leading-6 text-slate-200">{statement}</p>
                                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                      <FileText size={13} />
                                      <span>{trace?.source_chunk_ids?.length ? `Source ${trace.source_chunk_ids.join(', ')}` : 'Source pending'}</span>
                                      <span className="text-slate-700">|</span>
                                      <span className={trace?.confidence === 'high' ? 'text-emerald-300' : 'text-amber-300'}>{trace?.confidence || 'medium'} confidence</span>
                                    </div>
                                  </article>
                                );
                              }) : <p className="text-sm text-slate-500">No items found.</p>}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>
          </div>

          <div className={`space-y-5 ${activeView === 'architecture' ? '' : 'hidden'}`}>
            <Card className={activeView === 'architecture' ? '' : 'hidden'}>
              <div className="border-b border-slate-800 px-4 py-3">
                <h2 className="text-base font-semibold text-white">3. Research and architecture</h2>
                <p className="mt-1 text-xs text-slate-400">Choose the evidence policy, then create a reviewable architecture draft.</p>
              </div>
              <div className="space-y-4 p-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-xs font-medium text-slate-300">Evidence policy
                    <select value={researchMode} onChange={(event) => setResearchMode(event.target.value)} disabled={isBusy} className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-white outline-none focus:border-cyan-400">
                      <option value="azure_official_only">Azure official research</option>
                      <option value="azure_github_papers">Azure + GitHub + papers</option>
                      <option value="off">No web research</option>
                    </select>
                  </label>
                  <label className="text-xs font-medium text-slate-300">PowerPoint template
                    <select value={templateId} onChange={(event) => setTemplateId(event.target.value)} disabled={isBusy} className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-white outline-none focus:border-cyan-400">
                      <option value="starter">Starter</option>
                      <option value="fpt_fap">FPT FAP</option>
                      <option value="malaysia">Malaysia</option>
                      <option value="singapore">Singapore</option>
                      <option value="master_template">Enterprise master</option>
                    </select>
                  </label>
                </div>
                <div>
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:border-slate-500">
                    <FileUp size={16} /> {isUploadingReference ? 'Reading reference...' : 'Attach private reference'}
                    <input className="hidden" type="file" accept=".docx,.pdf,.txt,.md" onChange={uploadReferenceFile} disabled={isBusy || isUploadingReference} />
                  </label>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {privateReferences.map((reference, index) => (
                      <span key={`${reference.document_name}-${index}`} className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-300">
                        <FileText size={13} /> {reference.document_name}
                        <button type="button" title="Remove reference" onClick={() => setPrivateReferences((current) => current.filter((_, itemIndex) => itemIndex !== index))} className="ml-1 text-slate-500 hover:text-red-300"><X size={13} /></button>
                      </span>
                    ))}
                  </div>
                </div>
                <button type="button" onClick={() => setHitlDialog(architecture ? 'architecture' : 'requirements')} disabled={!extracted || isBusy} className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-violet-500 px-3 py-2.5 text-sm font-medium text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-40">
                  {activeOperation === 'research' ? <LoaderCircle className="animate-spin" size={17} /> : <Search size={17} />}
                  {architecture ? 'Open architecture review' : 'Complete requirement review'} <ArrowRight size={16} />
                </button>
                <p className="text-xs leading-5 text-slate-500">Architecture starts only after the consolidated requirement review is submitted.</p>

                {architecture && (
                  <div className="space-y-3 rounded-md border border-slate-700 bg-slate-950/65 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <StatusPill tone={architecture.research_status === 'completed' ? 'ready' : 'warning'}>Research {architecture.research_status || 'unknown'}</StatusPill>
                      <span className="text-xs text-slate-500">{RESEARCH_MODE_LABELS[researchMode] || 'Research'} - {architectureSources.length || 0} verified sources</span>
                    </div>
                    <p className="text-sm leading-6 text-slate-200">{architecture.architecture_summary}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(architecture.selected_patterns || []).map((pattern) => <span key={pattern} className="rounded border border-cyan-400/25 bg-cyan-400/5 px-2 py-1 text-xs text-cyan-100">{pattern}</span>)}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(architecture.components || []).slice(0, 6).map((component) => (
                        <div key={component.id || component.service} className="rounded border border-slate-800 bg-slate-900 p-2.5">
                          <p className="text-xs font-medium text-slate-100">{component.service}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{component.purpose}</p>
                        </div>
                      ))}
                    </div>
                    {!!architectureSources.length && (
                      <div className="space-y-2 border-t border-slate-800 pt-3">
                        <p className="text-xs font-medium uppercase tracking-normal text-slate-500">Evidence sources</p>
                        {architectureSources.slice(0, 8).map((source) => (
                          <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 truncate text-xs text-cyan-300 hover:text-cyan-200">
                            <Globe2 size={13} />
                            <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[11px] uppercase text-slate-400">{source.source_type || 'web'}</span>
                            <span className="truncate">{source.title}</span>
                          </a>
                        ))}
                      </div>
                    )}
                    <button type="button" onClick={() => setShowRawArchitecture((value) => !value)} className="text-xs text-slate-400 hover:text-slate-200">{showRawArchitecture ? 'Hide raw architecture JSON' : 'Inspect raw architecture JSON'}</button>
                    {showRawArchitecture && <pre className="max-h-64 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-300">{JSON.stringify(architecture, null, 2)}</pre>}
                  </div>
                )}
              </div>
            </Card>

          </div>
        </div>

        <Card className={activeView === 'proposal' ? '' : 'hidden'}>
          <div className="flex flex-col justify-between gap-3 border-b border-slate-800 px-4 py-3 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-base font-semibold text-white">4. Proposal and presentation</h2>
              <p className="mt-1 text-xs text-slate-400">Customer-ready content is generated after architecture approval.</p>
            </div>
            <div className="flex items-center gap-2">
              {!proposal && <button type="button" onClick={generateProposal} disabled={!architectureApproved || isBusy} className="inline-flex items-center gap-2 rounded-md bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40">
                {activeOperation === 'generate' ? <LoaderCircle className="animate-spin" size={16} /> : <WandSparkles size={16} />} Generate draft
              </button>}
              {downloadUrl && <a href={downloadUrl} className="text-sm text-cyan-300 hover:text-cyan-200">Download PPTX</a>}
              <button type="button" onClick={exportPpt} disabled={!proposal || !proposal.architecture_approved || isBusy} className="inline-flex items-center gap-2 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40">
                {activeOperation === 'export' ? <LoaderCircle className="animate-spin" size={16} /> : <Download size={16} />} Export PPTX
              </button>
            </div>
          </div>
          <div className="p-4">
            <div className="mb-4 grid gap-3 rounded-md border border-slate-800 bg-slate-950/50 p-3 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-300">Presentation pipeline
                <select value={presentationPipeline} onChange={(event) => setPresentationPipeline(event.target.value)} disabled={isBusy} className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-950 px-2.5 py-2 text-sm text-white outline-none focus:border-cyan-400">
                  {PRESENTATION_PIPELINES.map((pipeline) => (
                    <option key={pipeline.id} value={pipeline.id}>{pipeline.label}</option>
                  ))}
                </select>
              </label>
              <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3 text-xs leading-5 text-slate-400">
                <p className="font-medium text-slate-200">
                  {PRESENTATION_PIPELINES.find((pipeline) => pipeline.id === presentationPipeline)?.label}
                </p>
                <p className="mt-1">
                  {PRESENTATION_PIPELINES.find((pipeline) => pipeline.id === presentationPipeline)?.caption}
                </p>
                {presentationPipeline === 'deep_presenter' ? (
                  <p className="mt-2 text-amber-200/80">Requires the local `deeppresenter-host` Docker container to be running.</p>
                ) : presentationPipeline === 'master_template' ? (
                  <p className="mt-2 text-cyan-200/80">Uses the provided `master.pptx` structure and fills the predefined business, architecture, cost, risk, and next-step slides.</p>
                ) : (
                  <p className="mt-2 text-slate-500">Fastest path for predictable local PPT export.</p>
                )}
              </div>
            </div>
            {!proposal ? <p className="py-8 text-center text-sm text-slate-500">The architecture is approved. Generate the proposal draft when you are ready.</p> : (
              <ReactMarkdown className="prose prose-invert max-w-none prose-headings:font-semibold prose-p:text-slate-300 prose-li:text-slate-300">
                {[
                  `## Executive Summary\n${proposal.executive_summary}`,
                  proposal.expected_output ? `## Expected Output\n${proposal.expected_output.map((item) => `- ${item}`).join('\n')}` : '',
                  proposal.key_engineering_challenges ? `## Key Engineering Challenges\n${proposal.key_engineering_challenges.map((item) => `- ${item}`).join('\n')}` : '',
                  `## Business Solution\n${(proposal.business_solution || []).map((item) => `- ${item}`).join('\n')}`,
                  `## Technical Solution\n${(proposal.technical_solution || []).map((item) => `- ${item}`).join('\n')}`,
                  `## Infrastructure Design\n${(proposal.infrastructure_design || []).map((item) => `- ${item}`).join('\n')}`,
                ].filter(Boolean).join('\n\n')}
              </ReactMarkdown>
            )}
          </div>
        </Card>

        <footer className="flex items-center gap-2 pb-3 text-xs text-slate-600"><Clock3 size={13} /> Agent output remains a draft until the relevant human approval is recorded.</footer>
          </div>
        </div>
      </div>

      {hitlDialog === 'requirements' && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/80 p-4 backdrop-blur-sm sm:items-center" role="dialog" aria-modal="true" aria-labelledby="requirement-hitl-title">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-amber-400/30 bg-slate-900 shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
              <div><div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-amber-300"><CircleAlert size={15} /> Human review required</div><h2 id="requirement-hitl-title" className="text-lg font-semibold text-white">Clarify the requirement before architecture</h2><p className="mt-1 text-sm leading-6 text-slate-400">Answer the high-impact gaps, or explicitly record an assumption. The Architecture stage stays locked until this review is completed.</p></div>
              <button type="button" title="Review requirements first" onClick={() => setHitlDialog('')} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X size={18} /></button>
            </div>
            <div className="space-y-4 p-5">
              {(analysis?.clarification_questions || []).length === 0 && (
                <div className="rounded-md border border-slate-700 bg-slate-950/60 p-3 text-sm leading-6 text-slate-300">
                  No high-impact gap was raised by the Requirement Agent. You can continue without adding context, or provide an implementation note for the architect.
                </div>
              )}
              {(analysis?.clarification_questions || []).map((item, index) => (
                <div key={`${item.field}-${index}`} className="rounded-md border border-amber-400/20 bg-amber-400/5 p-3">
                  <p className="text-sm font-medium text-amber-50">{item.question}</p>
                  <p className="mt-1 text-xs leading-5 text-amber-100/60">{item.reason}</p>
                  {['yes_no', 'boolean'].includes(item.answer_type) ? (
                    <div className="mt-3 flex gap-2">
                      {['Yes', 'No'].map((option) => <button key={option} type="button" onClick={() => setClarifications((current) => ({ ...current, [item.field]: option }))} className={`rounded-md border px-3 py-2 text-sm ${clarifications[item.field] === option ? 'border-cyan-400 bg-cyan-400/15 text-cyan-100' : 'border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500'}`}>{option}</button>)}
                    </div>
                  ) : item.answer_type === 'single_select' && item.options?.length ? (
                    <select value={clarifications[item.field] || ''} onChange={(event) => setClarifications((current) => ({ ...current, [item.field]: event.target.value }))} className="mt-3 w-full rounded-md border border-slate-700 bg-slate-950 p-2.5 text-sm text-white outline-none focus:border-cyan-400">
                      <option value="">Select an answer</option>{item.options.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  ) : (
                    <textarea value={clarifications[item.field] || ''} onChange={(event) => setClarifications((current) => ({ ...current, [item.field]: event.target.value }))} placeholder={item.answer_type === 'number' ? 'Enter a numeric value' : 'Approved answer or explicit assumption'} className="mt-3 min-h-[82px] w-full resize-y rounded-md border border-slate-700 bg-slate-950 p-2.5 text-sm text-white outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400" />
                  )}
                  <button type="button" onClick={() => setClarifications((current) => ({ ...current, [item.field]: NO_ADDITIONAL_INFORMATION }))} className="mt-2 text-xs font-medium text-slate-400 hover:text-cyan-200">No additional information</button>
                </div>
              ))}
              <div className="rounded-md border border-slate-700 bg-slate-950/60 p-3">
                <label className="text-sm font-medium text-slate-200">Additional instruction for the architect <span className="font-normal text-slate-500">(optional)</span></label>
                <textarea value={clarifications.hitl_review === NO_ADDITIONAL_INFORMATION ? '' : clarifications.hitl_review || ''} onChange={(event) => setClarifications((current) => ({ ...current, hitl_review: event.target.value }))} placeholder="Example: prioritize low monthly cost over high availability for the POC." className="mt-2 min-h-[72px] w-full resize-y rounded-md border border-slate-700 bg-slate-950 p-2.5 text-sm text-white outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400" />
                <button
                  type="button"
                  onClick={() => {
                    setUseExternalEvidence((current) => {
                      const next = !current;
                      setResearchMode(next ? 'azure_github_papers' : 'azure_official_only');
                      return next;
                    });
                  }}
                  className={`mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition ${useExternalEvidence ? 'border-cyan-400 bg-cyan-400/15 text-cyan-100' : 'border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500 hover:text-white'}`}
                >
                  <Globe2 size={16} />
                  {useExternalEvidence ? 'Web search + GitHub/papers enabled' : 'Add web search + GitHub/papers to Architect prompt'}
                </button>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  Uses safe technical queries only. Customer content is not sent to public search.
                </p>
              </div>
            </div>
            <div className="flex flex-col-reverse gap-2 border-t border-slate-800 px-5 py-4 sm:flex-row sm:justify-end">
              <button type="button" onClick={() => setHitlDialog('')} className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">Review extracted output</button>
              <button type="button" onClick={continueFromRequirementHitl} className="inline-flex items-center justify-center gap-2 rounded-md bg-cyan-500 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-cyan-400">Confirm and unlock architecture <ArrowRight size={16} /></button>
            </div>
          </div>
        </div>
      )}

      {hitlDialog === 'architecture' && architecture && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/80 p-4 backdrop-blur-sm sm:items-center" role="dialog" aria-modal="true" aria-labelledby="architecture-hitl-title">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-emerald-400/30 bg-slate-900 shadow-2xl">
            <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
              <div><div className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-emerald-300"><BadgeCheck size={15} /> Architecture checkpoint</div><h2 id="architecture-hitl-title" className="text-lg font-semibold text-white">Review the architecture decision</h2><p className="mt-1 text-sm leading-6 text-slate-400">Confirm the selected services, evidence direction and environment costs before proposal content is generated.</p></div>
              <button type="button" title="Review architecture first" onClick={() => setHitlDialog('')} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X size={18} /></button>
            </div>
            <div className="space-y-4 p-5">
              <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3"><p className="text-sm leading-6 text-slate-200">{architecture.architecture_summary}</p><div className="mt-3 flex flex-wrap gap-1.5">{(architecture.selected_patterns || []).map((pattern) => <span key={pattern} className="rounded border border-cyan-400/25 bg-cyan-400/5 px-2 py-1 text-xs text-cyan-100">{pattern}</span>)}</div></div>
              {(architecture.decision_questions || []).length > 0 && <div className="rounded-md border border-amber-400/20 bg-amber-400/5 p-3"><p className="text-sm font-medium text-amber-100">Decision questions to validate</p><ul className="mt-2 space-y-1 text-sm text-amber-50/80">{architecture.decision_questions.map((question, index) => <li key={`${question}-${index}`}>- {typeof question === 'string' ? question : question.question || JSON.stringify(question)}</li>)}</ul></div>}
              <div><p className="mb-2 text-sm font-medium text-slate-200">Environment cost assumptions</p><div className="grid grid-cols-3 gap-2">{Object.entries(costAssumptions).map(([environment, value]) => <label key={environment} className="text-xs font-medium text-slate-400">{environment === 'uat_or_staging' ? 'UAT / Staging' : environment[0].toUpperCase() + environment.slice(1)}<input value={value} onChange={(event) => setCostAssumptions((current) => ({ ...current, [environment]: event.target.value }))} placeholder="USD/mo" className="mt-1.5 w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white outline-none focus:border-cyan-400" /></label>)}</div></div>
              <div><label className="text-sm font-medium text-slate-200">Request changes <span className="font-normal text-slate-500">(optional)</span></label><textarea value={architectureFeedback} onChange={(event) => setArchitectureFeedback(event.target.value)} placeholder="Example: use a lower-cost POC option and explain the production upgrade path." className="mt-2 min-h-[78px] w-full resize-y rounded-md border border-slate-700 bg-slate-950 p-2.5 text-sm text-white outline-none focus:border-cyan-400" /></div>
            </div>
            <div className="flex flex-col-reverse gap-2 border-t border-slate-800 px-5 py-4 sm:flex-row sm:justify-end">
              <button type="button" onClick={() => setHitlDialog('')} className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">Review architecture</button>
              <button type="button" onClick={requestArchitectureChanges} disabled={isBusy || !architectureFeedback.trim()} className="inline-flex items-center justify-center gap-2 rounded-md border border-amber-400/40 px-3 py-2 text-sm font-medium text-amber-100 hover:border-amber-300 disabled:cursor-not-allowed disabled:opacity-40">Request revision</button>
              <button type="button" onClick={approveArchitecture} className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-500 px-3 py-2 text-sm font-medium text-slate-950 hover:bg-emerald-400">Approve and unlock proposal <ArrowRight size={16} /></button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default SolutionArchitectProposalPage;
