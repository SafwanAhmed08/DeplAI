'use client';

interface ScansProps {
  projectId?: string;
}

export default function Scans({ projectId }: ScansProps) {
  return (
    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-gray-200 dark:border-[#1f1f1f] p-12">
      <div className="text-center">
        <div className="w-16 h-16 bg-gray-100 dark:bg-[#141414] rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Scans</h3>
        <p className="text-gray-500 dark:text-gray-400">Scan results will appear here</p>
      </div>
    </div>
  );
}