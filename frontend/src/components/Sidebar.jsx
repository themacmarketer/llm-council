import { useState } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
}) {
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  const startRename = (conv, e) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title || 'New Conversation');
  };

  const confirmRename = () => {
    if (editingId) {
      onRenameConversation(editingId, editTitle);
      setEditingId(null);
    }
  };

  const cancelRename = () => {
    setEditingId(null);
  };

  const handleDelete = (conv, e) => {
    e.stopPropagation();
    if (window.confirm(`Delete "${conv.title || 'New Conversation'}"?`)) {
      onDeleteConversation(conv.id);
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => {
                if (editingId !== conv.id) onSelectConversation(conv.id);
              }}
            >
              <div className="conversation-item-content">
                {editingId === conv.id ? (
                  <input
                    className="rename-input"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmRename();
                      if (e.key === 'Escape') cancelRename();
                    }}
                    onBlur={confirmRename}
                    autoFocus
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <div className="conversation-title">
                    {conv.title || 'New Conversation'}
                  </div>
                )}
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>
              <div className="conversation-actions" onClick={(e) => e.stopPropagation()}>
                <button
                  className="action-btn rename-btn"
                  title="Rename"
                  onClick={(e) => startRename(conv, e)}
                >
                  ✏️
                </button>
                <button
                  className="action-btn delete-btn"
                  title="Delete"
                  onClick={(e) => handleDelete(conv, e)}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
