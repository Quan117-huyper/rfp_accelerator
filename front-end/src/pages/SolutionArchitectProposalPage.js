import React, { useState } from 'react';
import { Download, FileUp, Loader, Search, Wand2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

const sampleRequirement = `Customer needs a secure internal AI assistant that can answer questions from company documents, enforce role-based access control, integrate with enterprise identity, and support thousands of users. The solution should preserve audit logs, protect confidential documents, and provide proposal content that can be exported to enterprise PowerPoint templates.`;

const Section = ({ title, children }) => (
  <div className="bg-gray-800 bg-opacity-50 rounded-lg p-4 shadow-lg">
    <h2 className="text-lg font-semibold text-blue-300 mb-3">{title}</h2>
    {children}
  </div>
);

const JsonPreview = ({ value }) => (
  <pre className="bg-gray-950 bg-opacity-70 rounded-md p-3 text-xs text-gray-100 overflow-auto max-h-72">
    {JSON.stringify(value, null, 2)}
  </pre>
);

const SolutionArchitectProposalPage = () => {
  const [documentText, setDocumentText] = useState(sampleRequirement);
  const [analysis, setAnalysis] = useState(null);
  const [clarifications, setClarifications] = useState({});
  const [research, setResearch] = useState(null);
  const [researchMode, setResearchMode] = useState('azure_official_only');
  const [privateReferences, setPrivateReferences] = useState([]);
  const [architectureApproved, setArchitectureApproved] = useState(false);
  const [costAssumptionsText, setCostAssumptionsText] = useState('[]');
  const [proposal, setProposal] = useState(null);
  const [templateId, setTemplateId] = useState('starter');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [isUploadingReference, setIsUploadingReference] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState('');
  const [error, setError] = useState('');

  const analyzeText = async () => {
    setIsAnalyzing(true);
    setError('');
    setDownloadUrl('');
    setResearch(null);
    try {
      const response = await fetch(`${API_BASE}/proposal/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_text: documentText }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Analyze failed');
      setAnalysis(data);
      setClarifications({});
      setPrivateReferences([]);
      setArchitectureApproved(false);
      setProposal(data.proposal);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const uploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsAnalyzing(true);
    setError('');
    setDownloadUrl('');
    setResearch(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/proposal/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Upload failed');
      setAnalysis(data);
      setClarifications({});
      setPrivateReferences([]);
      setArchitectureApproved(false);
      setProposal(data.proposal);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const runResearch = async () => {
    if (!analysis?.extracted) return;
    setIsResearching(true);
    setError('');
    setArchitectureApproved(false);
    try {
      const response = await fetch(`${API_BASE}/proposal/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extracted: analysis.extracted,
          clarifications,
          research_mode: researchMode,
          private_references: privateReferences,
          project_context: {
            delivery_stage: 'poc',
            cloud_preference: 'Azure',
            target_environments: ['development', 'test', 'uat_or_staging'],
            template_id: templateId,
          },
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Research failed');
      setResearch(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsResearching(false);
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
      const response = await fetch(`${API_BASE}/proposal/reference-upload`, {
        method: 'POST',
        body: formData,
      });
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
    if (!analysis?.extracted) return;
    setIsGenerating(true);
    setError('');
    try {
      const costAssumptions = JSON.parse(costAssumptionsText);
      if (!Array.isArray(costAssumptions)) {
        throw new Error('Cost assumptions must be a JSON array.');
      }
      const response = await fetch(`${API_BASE}/proposal/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extracted: analysis.extracted,
          clarifications,
          architecture_decisions: research?.architecture || null,
          cost_assumptions: costAssumptions,
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
      setIsGenerating(false);
    }
  };

  const exportPpt = async () => {
    if (!proposal) return;
    setIsExporting(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/proposal/export-pptx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal, template_id: templateId }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Export failed');
      setDownloadUrl(data.download_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto pr-2">
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <Wand2 className="text-blue-300" size={34} />
          <h1 className="text-3xl font-bold text-white">AI Solution Architect Proposal</h1>
        </div>
        <p className="text-gray-300 mt-2">
          Extract requirements, ask HITL questions, generate architecture and export a template-driven PPTX.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500 bg-red-950 bg-opacity-40 p-3 text-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Section title="Customer Requirement">
          <textarea
            className="w-full h-72 bg-gray-950 bg-opacity-70 rounded-md p-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={documentText}
            onChange={(event) => setDocumentText(event.target.value)}
          />
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              onClick={analyzeText}
              disabled={isAnalyzing || !documentText.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
            >
              {isAnalyzing ? <Loader className="animate-spin" size={18} /> : <Wand2 size={18} />}
              Analyze
            </button>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-gray-700 px-4 py-2 text-white">
              <FileUp size={18} />
              Upload DOCX/PDF/TXT
              <input className="hidden" type="file" accept=".docx,.pdf,.txt,.md" onChange={uploadFile} />
            </label>
          </div>
        </Section>

        <Section title="Extracted JSON">
          {analysis ? <JsonPreview value={analysis.extracted} /> : <p className="text-gray-400">Run analysis to see structured fields.</p>}
        </Section>

        <Section title="HITL Clarification">
          {analysis?.clarification_questions?.length ? (
            <ul className="space-y-3">
              {analysis.clarification_questions.map((item) => (
                <li key={item.field} className="rounded-md bg-gray-950 bg-opacity-50 p-3">
                  <div className="text-blue-200 font-medium">{item.question}</div>
                  <div className="text-sm text-gray-400 mt-1">{item.reason}</div>
                  <textarea
                    className="mt-2 w-full rounded-md bg-gray-900 p-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Add the approved clarification or assumption"
                    value={clarifications[item.field] || ''}
                    onChange={(event) => setClarifications((current) => ({
                      ...current,
                      [item.field]: event.target.value,
                    }))}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400">No missing fields detected yet.</p>
          )}
        </Section>

        <Section title="Research And Architecture">
          <label className="block text-sm font-medium text-gray-200">
            Research mode
            <select
              value={researchMode}
              onChange={(event) => setResearchMode(event.target.value)}
              className="mt-2 w-full rounded-md bg-gray-900 p-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="azure_official_only">Azure official sources only</option>
              <option value="off">No web research</option>
            </select>
          </label>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-gray-700 px-3 py-2 text-sm text-white">
              <FileUp size={16} />
              {isUploadingReference ? 'Reading reference...' : 'Add private reference'}
              <input
                className="hidden"
                type="file"
                accept=".docx,.pdf,.txt,.md"
                onChange={uploadReferenceFile}
                disabled={isUploadingReference}
              />
            </label>
            {privateReferences.map((reference, index) => (
              <button
                type="button"
                key={`${reference.document_name}-${index}`}
                onClick={() => setPrivateReferences((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                className="rounded-md border border-gray-600 px-2 py-1 text-xs text-gray-200 hover:border-red-400"
                title="Remove reference"
              >
                {reference.document_name} x
              </button>
            ))}
          </div>
          <button
            onClick={runResearch}
            disabled={!analysis?.extracted || isResearching}
            className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {isResearching ? <Loader className="animate-spin" size={18} /> : <Search size={18} />}
            Generate Architecture Draft
          </button>
          <p className="mt-3 text-sm text-gray-400">
            Private references stay in the proposal workflow. Web research uses only fixed Azure technical queries and never customer content.
          </p>
          {research ? (
            <div className="mt-3 space-y-3">
              <div className="text-sm text-gray-300">
                Research status: <span className="font-medium text-blue-200">{research.architecture?.research_status || 'unknown'}</span>
              </div>
              <JsonPreview value={research.architecture} />
              {research.sources?.length ? (
                <div className="text-sm">
                  <div className="mb-1 font-medium text-blue-200">Verified Sources</div>
                  <ul className="space-y-1">
                    {research.sources.map((source) => (
                      <li key={source.url}>
                        <a className="text-blue-300 underline" href={source.url} target="_blank" rel="noreferrer">
                          {source.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          <label className="mt-4 block text-sm font-medium text-gray-200">
            Approved cost assumptions (JSON)
            <textarea
              className="mt-2 h-24 w-full rounded-md bg-gray-900 p-2 font-mono text-xs text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={costAssumptionsText}
              onChange={(event) => setCostAssumptionsText(event.target.value)}
              placeholder={'[{"environment":"Development","monthly_estimate_usd":"TBD","notes":"Approved capacity assumptions"}]'}
            />
          </label>
          <label className="mt-4 flex items-center gap-2 text-sm text-gray-200">
            <input
              type="checkbox"
              checked={architectureApproved}
              onChange={(event) => setArchitectureApproved(event.target.checked)}
              disabled={!research?.architecture}
              className="h-4 w-4 accent-emerald-500"
            />
            Solution architect has approved this architecture
          </label>
          <button
            onClick={generateProposal}
            disabled={!analysis?.extracted || !research?.architecture || !architectureApproved || isGenerating}
            className="mt-3 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {isGenerating ? <Loader className="animate-spin" size={18} /> : <Wand2 size={18} />}
            Generate Final Proposal
          </button>
        </Section>

        <Section title="PPT Export">
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={templateId}
              onChange={(event) => setTemplateId(event.target.value)}
              className="rounded-md bg-gray-950 p-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="starter">Starter</option>
              <option value="fpt_fap">FPT FAP</option>
              <option value="malaysia">Malaysia</option>
              <option value="singapore">Singapore</option>
            </select>
            <button
              onClick={exportPpt}
              disabled={!proposal || !proposal.architecture_approved || isExporting}
              className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-white disabled:opacity-50"
            >
              {isExporting ? <Loader className="animate-spin" size={18} /> : <Download size={18} />}
              Export PPTX
            </button>
            {downloadUrl && (
              <a className="text-blue-300 underline" href={downloadUrl}>
                Download generated proposal
              </a>
            )}
          </div>
          <p className="mt-3 text-sm text-gray-400">
            Enterprise templates use placeholders like {'{{executive_summary}}'} and keep their existing layout.
          </p>
        </Section>
      </div>

        <Section title="Generated Proposal Draft">
        {proposal ? (
          <ReactMarkdown className="prose prose-invert max-w-none">
            {[
              `## Executive Summary\n${proposal.executive_summary}`,
              proposal.expected_output
                ? `## Expected Output\n${proposal.expected_output.map((item) => `- ${item}`).join('\n')}`
                : '',
              proposal.key_engineering_challenges
                ? `## Key Engineering Challenges\n${proposal.key_engineering_challenges.map((item) => `- ${item}`).join('\n')}`
                : '',
              `## Business Solution\n${proposal.business_solution.map((item) => `- ${item}`).join('\n')}`,
              `## Technical Solution\n${proposal.technical_solution.map((item) => `- ${item}`).join('\n')}`,
              `## Infrastructure Design\n${proposal.infrastructure_design.map((item) => `- ${item}`).join('\n')}`,
            ]
              .filter(Boolean)
              .join('\n\n')}
          </ReactMarkdown>
        ) : (
          <p className="text-gray-400">Proposal draft will appear here after analysis.</p>
        )}
      </Section>
    </div>
  );
};

export default SolutionArchitectProposalPage;
