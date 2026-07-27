import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

jest.mock('react-markdown', () => function ReactMarkdownMock({ children }) {
  return <div>{children}</div>;
});

const requirementResponse = {
  thread_id: 'proposal-test-thread',
  state: {
    status: 'awaiting_requirement_review',
    extraction: {
      extraction_mode: 'foundry_published_requirement_agent',
      extracted: {
        business_goals: ['Reduce proposal preparation time.'],
        functional_requirements: ['Upload RFP documents and extract requirements.'],
        non_functional_requirements: ['Target availability must be confirmed.'],
        constraints: [],
        assumptions: [],
        integrations: [],
        security_needs: ['Use project-scoped access control.'],
        expected_users: [],
      },
      traceability: {
        functional_requirements: [
          {
            statement: 'Upload RFP documents and extract requirements.',
            source_chunk_ids: ['doc-s01-c001'],
            confidence: 'high',
          },
        ],
      },
      clarification_questions: [
        {
          id: 'Q-001',
          field: 'availability_sla',
          question: 'What is the target availability SLA for the POC deployment?',
          reason: 'Needed before architecture approval.',
          answer_type: 'text',
        },
      ],
      ingestion: {
        stats: {
          pages: 1,
          chunks: 1,
          parser_pages: {},
        },
      },
      batch_count: 1,
    },
  },
  interrupt_payload: {
    type: 'requirement_review',
  },
};

const architectureResponse = {
  thread_id: 'proposal-test-thread',
  state: {
    status: 'awaiting_architecture_approval',
    research_mode: 'azure_github_papers',
    extraction: requirementResponse.state.extraction,
    clarifications: {
      availability_sla: 'Not specified. Record a solution architect assumption and validate it before implementation.',
      hitl_review: 'Use safe public web search with Azure official documentation, Microsoft/Azure GitHub repositories, and relevant public research papers to support architecture decisions.',
    },
    research_result: {
      mode: 'foundry_published_architect_agent',
      sources: [
        {
          title: 'Azure AI Search docs',
          url: 'https://learn.microsoft.com/azure/search/',
          source_type: 'azure_docs',
        },
        {
          title: 'Microsoft sample repository',
          url: 'https://github.com/microsoft/sample',
          source_type: 'microsoft_github',
        },
        {
          title: 'RAG paper',
          url: 'https://arxiv.org/abs/2005.11401',
          source_type: 'research_paper',
        },
      ],
      architecture: {
        research_status: 'completed',
        architecture_summary: 'Use Azure services with cited docs, Microsoft GitHub samples, and public papers.',
        selected_patterns: ['Workflow automation'],
        components: [
          {
            id: 'ARC-001',
            service: 'Azure AI Document Intelligence',
            purpose: 'OCR and layout extraction.',
          },
        ],
        research_sources: [
          {
            title: 'Azure AI Search docs',
            url: 'https://learn.microsoft.com/azure/search/',
            source_type: 'azure_docs',
          },
          {
            title: 'Microsoft sample repository',
            url: 'https://github.com/microsoft/sample',
            source_type: 'microsoft_github',
          },
          {
            title: 'RAG paper',
            url: 'https://arxiv.org/abs/2005.11401',
            source_type: 'research_paper',
          },
        ],
      },
    },
  },
  interrupt_payload: {
    type: 'architecture_review',
  },
};

beforeEach(() => {
  window.localStorage.clear();
  global.fetch = jest.fn((url) => {
    if (String(url).includes('/proposal/hitl/start')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(requirementResponse),
      });
    }
    if (String(url).includes('/proposal/hitl/proposal-test-thread/resume')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(architectureResponse),
      });
    }
    return Promise.reject(new Error(`Unexpected fetch: ${url}`));
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('unlocks architecture and sends GitHub/papers research mode from HITL review', async () => {
  render(<App />);

  fireEvent.click(screen.getByRole('button', { name: /analyze requirement/i }));

  expect(await screen.findByText(/Clarify the requirement before architecture/i)).toBeInTheDocument();

  await waitFor(() => {
    screen.getAllByRole('button', { name: /Architecture/i }).forEach((button) => {
      expect(button).not.toBeDisabled();
    });
  });

  fireEvent.click(screen.getByRole('button', { name: /Add web search \+ GitHub\/papers to Architect prompt/i }));
  fireEvent.click(screen.getByRole('button', { name: /Confirm and unlock architecture/i }));

  expect((await screen.findAllByText(/Use Azure services with cited docs/i)).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/microsoft_github/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/research_paper/i).length).toBeGreaterThan(0);

  const resumeCall = global.fetch.mock.calls.find(([url]) => String(url).includes('/proposal/hitl/proposal-test-thread/resume'));
  expect(resumeCall).toBeTruthy();
  const payload = JSON.parse(resumeCall[1].body);
  expect(payload.research_mode).toBe('azure_github_papers');
  expect(payload.additional_instruction).toMatch(/GitHub repositories/);
});
