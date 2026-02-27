import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import CopyButton from './CopyButton';
import './Stage0.css';

export default function Stage0({ research }) {
  const [showDetails, setShowDetails] = useState(false);

  if (!research || !research.has_research) {
    return null;
  }

  return (
    <div className="stage stage0">
      <h3 className="stage-title">Stage 0: Web Research</h3>
      <div className="research-content">
        <div className="research-header">
          <div className="research-model">{research.model}</div>
          <CopyButton content={research.response} />
        </div>
        <div className="research-text markdown-content">
          <ReactMarkdown>{research.response}</ReactMarkdown>
        </div>
      </div>

      {research.sub_results?.length > 1 && (
        <>
          <button
            className="details-toggle"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? 'Hide' : 'Show'} individual research ({research.sub_results.length} queries)
          </button>

          {showDetails && research.sub_results.map((sub, i) => (
            <div key={i} className="sub-research-item">
              <div className="sub-research-header">
                <div className="sub-research-query">{sub.query}</div>
                <CopyButton content={sub.response} />
              </div>
              <div className="sub-research-text markdown-content">
                <ReactMarkdown>{sub.response}</ReactMarkdown>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
