'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import ExitIcon from '@/components/exit-button';
import ThemeToggle from '@/components/theme-toggle';
import Scans from '../scans';
import Findings from '../findings';

type ActiveTab = 'scans' | 'findings';

export default function SecurityAnalysisPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.projectId as string;

  const [activeTab, setActiveTab] = useState<ActiveTab>('scans');
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjectInfo();
  }, [projectId]);

  async function fetchProjectInfo() {
    try {
      const res = await fetch('/api/projects');
      const data = await res.json();
      const foundProject = (data.projects || []).find((p: any) => p.id === projectId);
      setProject(foundProject);
    } catch (error) {
      console.error('Failed to fetch project:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/');
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-black flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-black">
      {/* Header */}
      <header className="bg-white dark:bg-[#0a0a0a] border-b border-gray-200 dark:border-[#1f1f1f] sticky top-0 z-10">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-xl font-bold text-gray-900 dark:text-white">Security Analysis</span>
            </div>

            <div className="flex items-center space-x-2">
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="p-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-[#1a1a1a] rounded-lg transition"
                title="Logout"
              >
                <ExitIcon />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-6 py-8">
        {/* Back Button and Project Info */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-4">
            <Link
              href="/dashboard"
              className="hover:opacity-70 transition"
              title="Back to Dashboard"
            >
              <svg
                width="24"
                height="25"
                viewBox="0 0 24 25"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="dark:invert"
              >
                <path
                  d="M18.125 6.62502C18.125 6.32168 17.9423 6.0482 17.662 5.93211C17.3818 5.81603 17.0592 5.88019 16.8447 6.09469L10.5947 12.3447C10.3018 12.6376 10.3018 13.1125 10.5947 13.4054L16.8447 19.6554C17.0592 19.8699 17.3818 19.934 17.662 19.8179C17.9423 19.7018 18.125 19.4284 18.125 19.125V6.62502Z"
                  fill="#323544"
                />
                <path
                  d="M13.4053 7.15535C13.6982 6.86246 13.6982 6.38758 13.4053 6.09469C13.1124 5.8018 12.6376 5.8018 12.3447 6.09469L6.09467 12.3447C5.80178 12.6376 5.80178 13.1125 6.09467 13.4054L12.3447 19.6554C12.6376 19.9482 13.1124 19.9482 13.4053 19.6554C13.6982 19.3625 13.6982 18.8876 13.4053 18.5947L7.68566 12.875L13.4053 7.15535Z"
                  fill="#323544"
                />
              </svg>
            </Link>
          </div>

        </div>

        {/* Tab Navigation */}
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-gray-200 dark:border-[#1f1f1f] mb-8">
          <div className="flex border-b border-gray-200 dark:border-[#1f1f1f]">
            <button
              onClick={() => setActiveTab('scans')}
              className={`flex-1 px-6 py-4 text-sm font-medium transition ${
                activeTab === 'scans'
                  ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
              }`}
            >
              Scans
            </button>
            <button
              onClick={() => setActiveTab('findings')}
              className={`flex-1 px-6 py-4 text-sm font-medium transition ${
                activeTab === 'findings'
                  ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
              }`}
            >
              Findings
            </button>
          </div>
        </div>

        {/* Content Area */}
        {activeTab === 'scans' && <Scans projectId={projectId} />}
        {activeTab === 'findings' && <Findings projectId={projectId} />}
      </div>
    </div>
  );
}
