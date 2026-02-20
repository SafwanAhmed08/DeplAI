'use client';

import { useState } from 'react';
import { usePopup } from '@/components/popup';
import { FiGlobe, FiLink, FiShield } from 'react-icons/fi';

interface ScanModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: {
    id: string;
    name?: string;
    repo?: string;
    owner?: string;
    installationId?: string;
    type: 'local' | 'github';
  } | null;
  onScanComplete: (result: ScanResult) => void;
}

interface ScanResult {
  projectId: string;
  projectName: string;
  dastEnabled: boolean;
  dastUrl?: string;
  securityAnalysis: boolean;
  scanId?: string;
  scanStatus?: string;
}

type Step = 'dast' | 'dast-url' | 'security';

export default function ScanModal({ isOpen, onClose, project, onScanComplete }: ScanModalProps) {
  const { showPopup } = usePopup();
  const [step, setStep] = useState<Step>('dast');
  const [dastUrl, setDastUrl] = useState('');
  const [urlError, setUrlError] = useState('');
  const [validating, setValidating] = useState(false);
  const [dastEnabled, setDastEnabled] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen || !project) return null;

  const projectName = project.type === 'local' ? project.name : project.repo;

  const resetModal = () => {
    setStep('dast');
    setDastUrl('');
    setUrlError('');
    setValidating(false);
    setDastEnabled(false);
    setSubmitting(false);
  };

  const handleClose = () => {
    resetModal();
    onClose();
  };

  const handleDastYes = () => {
    setDastEnabled(true);
    setStep('dast-url');
  };

  const handleDastNo = () => {
    setDastEnabled(false);
    setStep('security');
  };

  const validateUrl = async () => {
    if (!dastUrl.trim()) {
      setUrlError('Please enter a URL');
      return;
    }

    try {
      new URL(dastUrl);
    } catch {
      setUrlError('Please enter a valid URL');
      return;
    }

    setValidating(true);
    setUrlError('');

    try {
      const response = await fetch('/api/validate-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: dastUrl }),
      });

      const data = await response.json();

      if (data.valid) {
        setStep('security');
      } else {
        setUrlError(data.error || 'URL is not reachable');
      }
    } catch {
      setUrlError('Failed to validate URL');
    } finally {
      setValidating(false);
    }
  };

  const handleRetry = () => {
    setUrlError('');
    setDastUrl('');
  };

  const handleSkipDast = () => {
    setDastEnabled(false);
    setDastUrl('');
    setStep('security');
  };

  const handleSecurityAnalysis = async (performAnalysis: boolean) => {
    setSubmitting(true);

    try {
      const scanConfig: ScanResult = {
        projectId: project.id,
        projectName: projectName || 'Unknown',
        dastEnabled: dastEnabled && !!dastUrl,
        dastUrl: dastEnabled ? dastUrl : undefined,
        securityAnalysis: performAnalysis,
      };

      // Call the Next.js API route (which forwards to the backend)
      const response = await fetch('/api/scan/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: project.id,
          project_name: projectName || 'Unknown',
          project_type: project.type,
          deployment_url: dastEnabled ? dastUrl : undefined,
          // GitHub-specific fields
          installation_id: project.installationId,
          owner: project.owner,
          repo: project.repo,
        }),
      });

      if (!response.ok) {
        throw new Error('Backend request failed');
      }

      const data = await response.json();
      console.log('Backend response:', data);

      let resolvedScanStatus = 'not-started';
      if (data?.scan_id) {
        const scanId = data.scan_id as string;
        resolvedScanStatus = 'running';

        for (let attempt = 0; attempt < 30; attempt += 1) {
          const statusResponse = await fetch(`/api/scan/status/${scanId}`, {
            method: 'GET',
            cache: 'no-store',
          });

          if (!statusResponse.ok) {
            break;
          }

          const statusPayload = await statusResponse.json();
          const status = statusPayload?.status as string | undefined;

          if (status === 'completed' || status === 'failed') {
            resolvedScanStatus = status;

            const resultsResponse = await fetch(`/api/scan/results/${scanId}`, {
              method: 'GET',
              cache: 'no-store',
            });

            if (resultsResponse.ok) {
              const resultsPayload = await resultsResponse.json();
              console.log('Scan results:', resultsPayload);
            }
            break;
          }

          await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        scanConfig.scanId = scanId;
        scanConfig.scanStatus = resolvedScanStatus;
      }

      onScanComplete(scanConfig);
      handleClose();
    } catch (error) {
      console.error('Failed to initiate scan:', error);
      showPopup({
        type: 'error',
        message: 'Failed to connect to the backend. Please ensure the server is running.',
      });
      handleClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center font-sans">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />

      {/* Modal Content */}
      <div className="relative bg-white dark:bg-[#0a0a0a] rounded-xl shadow-2xl w-full max-w-[480px] mx-4 overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200">

        {/* Header */}
        <div className="px-6 py-5">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white leading-tight">
            Scan Project
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {projectName || 'DeplAI'}
          </p>
        </div>

        <hr className="border-gray-100 dark:border-[#1f1f1f]" />

        {/* Content Area */}
        <div className="p-8 pt-6">

          {/* --- Step 1: DAST Check --- */}
          {step === 'dast' && (
            <div className="flex flex-col items-center">
              <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mb-6">
                <FiGlobe className="w-10 h-10 text-blue-600 dark:text-blue-400" />
              </div>

              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 text-center">
                DAST
              </h3>

              <p className="text-gray-600 dark:text-gray-400 text-center leading-relaxed mb-8 max-w-sm">
                Do you have a live deployment of your project that we can use to perform Dynamic Application Security Testing
              </p>

              <div className="flex gap-4 w-full">
                <button
                  onClick={handleDastYes}
                  className="flex-1 py-3 px-4 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold rounded-lg transition shadow-sm"
                >
                  Yes
                </button>
                <button
                  onClick={handleDastNo}
                  className="flex-1 py-3 px-4 bg-gray-200 hover:bg-gray-300 dark:bg-[#141414] dark:hover:bg-[#222] text-gray-900 dark:text-white font-semibold rounded-lg transition"
                >
                  No
                </button>
              </div>
            </div>
          )}

          {/* --- Step 1.5: DAST URL Input (Kept consistent with style) --- */}
          {step === 'dast-url' && (
            <div className="flex flex-col items-center">
              <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mb-6">
                <FiLink className="w-10 h-10 text-blue-600 dark:text-blue-400" />
              </div>

              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 text-center">
                Enter Live Application URL
              </h3>

              <div className="w-full mb-6">
                <input
                  type="url"
                  value={dastUrl}
                  onChange={(e) => {
                    setDastUrl(e.target.value);
                    setUrlError('');
                  }}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-[#2a2a2a] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition bg-white dark:bg-[#141414] text-gray-900 dark:text-white"
                  autoFocus
                />
                {urlError && (
                   <p className="text-red-600 text-sm mt-2 ml-1">{urlError}</p>
                )}
              </div>

              <div className="flex gap-4 w-full">
                <button
                  onClick={validateUrl}
                  disabled={validating}
                  className="flex-1 py-3 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-70 text-white font-semibold rounded-lg transition shadow-sm flex justify-center items-center"
                >
                  {validating ? 'Validating...' : 'Next'}
                </button>
                <button
                   onClick={() => setStep('dast')}
                   className="flex-1 py-3 px-4 bg-gray-200 hover:bg-gray-300 dark:bg-[#141414] text-gray-900 dark:text-white font-semibold rounded-lg transition"
                >
                  Back
                </button>
              </div>
            </div>
          )}

          {/* --- Step 2: Security Analysis --- */}
          {step === 'security' && (
            <div className="flex flex-col items-center">
              <div className="w-20 h-20 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-6">
                <FiShield className="w-10 h-10 text-green-600 dark:text-green-500" />
              </div>

              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 text-center">
                Confirmation
              </h3>

              <p className="text-gray-600 dark:text-gray-400 text-center leading-relaxed mb-6">
                Do you want to perform a security scan?
              </p>

              {/* DAST Enabled Box - Matches Image 2 */}
              {dastEnabled && dastUrl && (
                <div className="w-full mb-8 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-lg text-left">
                  <p className="text-xs font-semibold text-blue-500 dark:text-blue-400 uppercase tracking-wide mb-1">
                    DAST Enabled
                  </p>
                  <p className="text-sm text-blue-700 dark:text-blue-300 truncate font-medium">
                    {dastUrl}
                  </p>
                </div>
              )}

              {!dastEnabled && <div className="mb-8" />}

              {submitting ? (
                <div className="flex flex-col items-center gap-4 w-full py-2">
                  <div className="w-10 h-10 border-4 border-green-200 dark:border-green-900 border-t-green-600 dark:border-t-green-500 rounded-full animate-spin" />
                  <p className="text-sm text-gray-600 dark:text-gray-400 font-medium">
                    Starting scan...
                  </p>
                </div>
              ) : (
                <div className="flex gap-4 w-full">
                  <button
                    onClick={() => handleSecurityAnalysis(true)}
                    className="flex-1 py-3 px-4 bg-green-600 hover:bg-green-700 active:bg-green-800 text-white font-semibold rounded-lg transition shadow-sm"
                  >
                    Yes
                  </button>
                  <button
                    onClick={handleClose}
                    className="flex-1 py-3 px-4 bg-gray-200 hover:bg-gray-300 dark:bg-[#141414] dark:hover:bg-[#222] text-gray-900 dark:text-white font-semibold rounded-lg transition"
                  >
                    No
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
