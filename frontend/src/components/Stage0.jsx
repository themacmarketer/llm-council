import ReactMarkdown from 'react-markdown';
import './Stage0.css';

export default function Stage0({ research }) {
  if (!research || !research.has_research) {
    return null;
  }

  return (
    <div className="stage stage0">
      <h3 className="stage-title">Stage 0: Web Research</h3>
      <div className="research-content">
        <div className="research-model">{research.model}</div>
        <div className="research-text markdown-content">
          <ReactMarkdown>{research.response}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
