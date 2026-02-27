import { useState, useRef, useEffect } from "react";
import { Settings } from "lucide-react";
import "./settings-button.css";

interface SettingsButtonProps {
  onSettingsChange?: () => void; // Optional callback to notify parent component when settings change
}

export default function SettingsButton({
  onSettingsChange
}: SettingsButtonProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<"layer" | "about">(
    "layer"
  );
  const [firBoundary, setFirBoundary] = useState(() => {
    const saved = localStorage.getItem("fir-boundary");
    return saved ? JSON.parse(saved) : false;
  });
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
    // Save fir-boundary to local storage
    localStorage.setItem("fir-boundary", JSON.stringify(firBoundary));

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
        title="Settings"
      >
        <Settings size={16} />
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
            <div className="settings-modal-layout">
              <div className="settings-sidebar">
                <button
                  className={`settings-sidebar-item ${
                    activeSection === "layer" ? "active" : ""
                  }`}
                  onClick={() => setActiveSection("layer")}
                >
                  Layer
                </button>
                <button
                  className={`settings-sidebar-item ${
                    activeSection === "about" ? "active" : ""
                  }`}
                  onClick={() => setActiveSection("about")}
                >
                  About
                </button>
              </div>
              <div className="settings-content">
                {activeSection === "layer" && (
                  <div className="settings-modal-body">
                    <div className="settings-form-group settings-switch-group">
                      <label
                        htmlFor="fir-boundary"
                        className="settings-switch-label"
                      >
                        FIR Boundary
                      </label>
                      <button
                        id="fir-boundary"
                        className={`settings-switch ${
                          firBoundary ? "active" : ""
                        }`}
                        onClick={() => setFirBoundary(!firBoundary)}
                        role="switch"
                        aria-checked={firBoundary}
                      >
                        <span className="settings-switch-thumb" />
                      </button>
                    </div>
                  </div>
                )}
                {activeSection === "about" && (
                  <div className="settings-modal-body settings-about">
                    <div className="about-content">
                      <h2 className="about-title">Twilight</h2>
                      <p className="about-description">
                        A Himawari Satellite Data Visualization System
                      </p>
                      <p className="about-version">
                        <a
                          href="https://github.com/up1and/twilight"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          v0.1
                        </a>
                      </p>
                      <p className="about-copyright">
                        Copyright © 2025{" "}
                        <a href="mailto:piratecb@gmail.com">up1and</a>
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="settings-modal-footer">
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
