import { useState, useRef, useEffect } from "react";
import { getApiConfig, setApiConfig } from "../utils/api-client";
import "./settings-button.css";

interface SettingsButtonProps {
  onSettingsChange?: () => void; // Optional callback to notify parent component when settings change
}

export default function SettingsButton({
  onSettingsChange,
}: SettingsButtonProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [endpoint, setEndpoint] = useState(getApiConfig().endpoint);
  const [token, setToken] = useState(getApiConfig().token);
  const modalRef = useRef<HTMLDivElement>(null);

  // Close modal when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        modalRef.current &&
        !modalRef.current.contains(event.target as Node) &&
        isModalOpen
      ) {
        // Only close if clicking outside the modal content
        if (!(event.target as HTMLElement).closest(".settings-modal-content")) {
          setIsModalOpen(false);
        }
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isModalOpen]);

  const handleSave = () => {
    // Save settings using the API client utility
    setApiConfig({
      endpoint,
      token,
    });

    // Call the callback function if provided to notify the parent component
    if (onSettingsChange) {
      onSettingsChange();
    }

    setIsModalOpen(false);
  };

  return (
    <>
      <button
        className="settings-button"
        onClick={() => setIsModalOpen(true)}
        aria-label="Settings"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      </button>

      {isModalOpen && (
        <div className="settings-modal" ref={modalRef}>
          <div className="settings-modal-content">
            <div className="settings-modal-header">
              <h3>Settings</h3>
              <button
                className="settings-modal-close"
                onClick={() => setIsModalOpen(false)}
              >
                ×
              </button>
            </div>
            <div className="settings-modal-body">
              <div className="settings-form-group">
                <label htmlFor="endpoint">Endpoint</label>
                <input
                  id="endpoint"
                  type="text"
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  placeholder="https://example.com"
                />
              </div>
              <div className="settings-form-group">
                <label htmlFor="token">Token</label>
                <input
                  id="token"
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Enter your token"
                />
              </div>
            </div>
            <div className="settings-modal-footer">
              <button
                className="settings-button-action secondary"
                onClick={() => setIsModalOpen(false)}
              >
                Cancel
              </button>
              <button
                className="settings-button-action primary"
                onClick={handleSave}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
