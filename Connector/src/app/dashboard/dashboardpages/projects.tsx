'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import ProjectIcon from '@/components/project-icons';
import { SearchIcon, FileXmarkIcon, FilterIcon } from '@/components/search-result';
import { ArrowLeftCircle, ArrowRightCircle } from '@/components/pagination-arrows';
import { FileFormatZip, FilePlusCircle, DownloadIcon } from '@/components/upload-icon';
import ScanModal from '@/components/scan-card';
import { usePopup } from '@/components/popup';

interface ProjectsProps {
  user: any;
  installations: any[];
  projects: any[];
  stats: { localCount: number; githubCount: number; totalCount: number };
  loading: boolean;
  uploading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement>;
  handleFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleDeleteProject: (projectId: string, projectName: string) => void;
  handleProjectClick: (project: any) => void;
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

const PROJECTS_PER_PAGE = 5;

export default function Projects({
  user,
  installations,
  projects,
  stats,
  loading,
  uploading,
  fileInputRef,
  handleFileUpload,
  handleDeleteProject,
  handleProjectClick,
}: ProjectsProps) {
  const { showPopup } = usePopup();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [filter, setFilter] = useState<'none' | 'github' | 'local'>('none');
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);
  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<any>(null);

  // Handle opening scan modal
  const handleScanClick = (project: any) => {
    setSelectedProject(project);
    setScanModalOpen(true);
  };

  // Handle scan completion
  const handleScanComplete = (result: ScanResult) => {
    const features = [];
    if (result.dastEnabled) features.push('DAST');
    if (result.securityAnalysis) features.push('Security Analysis');

    if (features.length > 0) {
      const scanInfo = result.scanId
        ? ` Scan ID: ${result.scanId}. Status: ${result.scanStatus ?? 'running'}.`
        : '';
      showPopup({
        type: 'success',
        message: `Scan initiated for "${result.projectName}" with ${features.join(' and ')}.${scanInfo}`,
      });
    } else {
      showPopup({
        type: 'info',
        message: `No scan options selected for "${result.projectName}".`,
      });
    }
  };

  // Filter projects based on search query and filter type
  const filteredProjects = useMemo(() => {
    let result = projects;

    // Apply type filter
    if (filter === 'github') {
      result = result.filter((project) => project.type === 'github');
    } else if (filter === 'local') {
      result = result.filter((project) => project.type === 'local');
    }

    // Apply search filter (case-insensitive)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((project) => {
        const name = project.type === 'local' ? project.name : project.repo;
        return name?.toLowerCase().includes(query);
      });
    }

    return result;
  }, [projects, searchQuery, filter]);

  // Calculate pagination
  const totalPages = Math.ceil(filteredProjects.length / PROJECTS_PER_PAGE);
  const startIndex = (currentPage - 1) * PROJECTS_PER_PAGE;
  const paginatedProjects = filteredProjects.slice(startIndex, startIndex + PROJECTS_PER_PAGE);

  // Reset to page 1 when search query changes
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  // Handle filter change
  const handleFilterChange = (newFilter: 'none' | 'github' | 'local') => {
    setFilter(newFilter);
    setCurrentPage(1);
    setShowFilterDropdown(false);
  };

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(prev - 1, 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(prev + 1, totalPages));
  };

  // Open GitHub App permissions in a popup window
  const handleConnectRepository = () => {
    const url = 'https://github.com/apps/DeplAISafwan/installations/new';
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;

    const popup = window.open(
      url,
      'github-connect',
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes,resizable=yes`
    );

    // Poll to detect when popup is closed
    const checkClosed = setInterval(() => {
      if (popup?.closed) {
        clearInterval(checkClosed);
        // Refresh the page to fetch updated repositories
        window.location.reload();
      }
    }, 500);
  };

  return (
    <div className="grid lg:grid-cols-3 gap-6 mt-15">
      <div className="lg:col-span-1 space-y-6">
        {/* Upload Project Section - Dashed Dropzone */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          onChange={handleFileUpload}
          className="hidden"
          disabled={uploading}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full p-8 rounded-xl border-2 border-dashed border-gray-300 dark:border-[#333] bg-gray-50 dark:bg-[#111]/50 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed group"
        >
          <div className="flex flex-col items-center">
            {uploading ? (
              <div className="animate-spin w-12 h-12 border-3 border-blue-600 border-t-transparent rounded-full"></div>
            ) : (
              <FileFormatZip className="w-12 h-12 text-gray-400 dark:text-gray-500 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors" />
            )}
            <p className="mt-3 text-sm font-medium text-gray-600 dark:text-gray-300 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
              {uploading ? 'Uploading...' : 'Upload Project'}
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              .zip files up to 10 GB
            </p>
          </div>
        </button>

        {/* Connect Repository Section - Only shown when GitHub App is installed */}
        {installations.length > 0 && (
          <button
            onClick={handleConnectRepository}
            className="w-full p-8 rounded-xl border-2 border-dashed border-gray-300 dark:border-[#333] bg-gray-50 dark:bg-[#111]/50 hover:border-gray-400 dark:hover:border-gray-500 hover:bg-gray-100 dark:hover:bg-[#222]/50 transition-all duration-200 cursor-pointer group"
          >
            <div className="flex flex-col items-center">
              <FilePlusCircle className="w-12 h-12 text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors" />
              <p className="mt-3 text-sm font-medium text-gray-600 dark:text-gray-300 group-hover:text-gray-800 dark:group-hover:text-white transition-colors">
                Connect Repository
              </p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Add GitHub repositories
              </p>
            </div>
          </button>
        )}

        {/* GitHub Installations */}
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-gray-200 dark:border-[#1f1f1f]">
          <div className="p-6 border-b border-gray-200 dark:border-[#1f1f1f]">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">GitHub Accounts</h2>
          </div>

          <div className="p-4">
            {installations.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-gray-100 dark:bg-[#141414] rounded-full flex items-center justify-center mx-auto mb-4">
                  <DownloadIcon className="w-8 h-8 text-gray-400" />
                </div>
                <p className="text-gray-600 dark:text-gray-300 font-medium mb-2">No installations yet</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Install the GitHub App to get started</p>
                <a
                  href="https://github.com/apps/DeplAISafwan/installations/new"
                  className="inline-block bg-blue-600 dark:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 dark:hover:bg-blue-600 transition"
                >
                  Install GitHub App
                </a>
              </div>
            ) : (
              <div className="space-y-2">
                {installations.map((inst) => (
                  <a
                    key={inst.id}
                    href={`https://github.com/${inst.account_login}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-4 rounded-lg bg-gray-50 dark:bg-[#141414] border-2 border-transparent cursor-pointer transition-all duration-200 hover:bg-gray-100 dark:hover:bg-[#222]"
                  >
                    <div className="flex items-center space-x-3">
                      <img
                        src={user?.avatarUrl || `https://github.com/${inst.account_login}.png`}
                        alt={inst.account_login}
                        className="w-10 h-10 rounded-full"
                      />
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 dark:text-white">{inst.account_login}</h3>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{inst.account_type}</p>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Projects Main Panel */}
      <div className="lg:col-span-2">
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-gray-200 dark:border-[#1f1f1f]">
          {/* Search Bar */}
          <div className="p-6 border-b border-gray-200 dark:border-[#1f1f1f]">
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search"
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-200 dark:border-[#2a2a2a] bg-gray-50 dark:bg-[#141414] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
              <div className="relative">
                <button
                  onClick={() => setShowFilterDropdown(!showFilterDropdown)}
                  className={`p-2.5 rounded-lg border transition ${
                    filter !== 'none'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                      : 'border-gray-200 dark:border-[#2a2a2a] bg-gray-50 dark:bg-[#141414] text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#222]'
                  }`}
                >
                  <FilterIcon className="w-5 h-5" />
                </button>
                {showFilterDropdown && (
                  <div className="absolute right-0 mt-2 w-36 bg-white dark:bg-[#141414] border border-gray-200 dark:border-[#2a2a2a] rounded-lg shadow-lg z-10">
                    <button
                      onClick={() => handleFilterChange('none')}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-[#222] rounded-t-lg ${
                        filter === 'none' ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      None
                    </button>
                    <button
                      onClick={() => handleFilterChange('github')}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-[#222] ${
                        filter === 'github' ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      GitHub
                    </button>
                    <button
                      onClick={() => handleFilterChange('local')}
                      className={`w-full px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-[#222] rounded-b-lg ${
                        filter === 'local' ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      Local
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="p-6 max-h-[500px] overflow-y-auto">
            {loading ? (
              <div className="text-center py-12">
                <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto"></div>
                <p className="text-gray-500 dark:text-gray-400 mt-4">Loading projects...</p>
              </div>
            ) : projects.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-600 dark:text-gray-300 font-medium mb-2">No projects yet</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Upload a local project or install the GitHub App</p>
              </div>
            ) : filteredProjects.length === 0 ? (
              <div className="text-center py-12">
                <FileXmarkIcon className="mx-auto text-gray-400 dark:text-gray-500 mb-4" />
                <p className="text-gray-600 dark:text-gray-300 font-medium mb-2">No projects found</p>
              </div>
            ) : (
              <div className="space-y-4">
                {paginatedProjects.map((project) => (
                  <div
                    key={project.id}
                    className="group border border-gray-200 dark:border-[#2a2a2a] rounded-lg p-5 hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all duration-300 cursor-pointer bg-white dark:bg-[#141414]"
                    onClick={() => handleProjectClick(project)}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center space-x-3">
                        <ProjectIcon type={project.type} size={40} className="text-gray-700 dark:text-gray-300" />
                        <div>
                          <h3 className="font-semibold text-gray-900 dark:text-white">
                            {project.type === 'local' ? project.name : project.repo}
                          </h3>
                          <div className="flex items-center space-x-3 mt-1">
                            {project.type === 'local' ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300">
                                Local
                              </span>
                            ) : (
                              <>
                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                  project.access === 'Private'
                                    ? 'bg-orange-100 dark:bg-orange-900 text-orange-700 dark:text-orange-300'
                                    : 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300'
                                }`}>
                                  {project.access}
                                </span>
                                {project.branch && (
                                  <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {project.branch}
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        {project.canDelete && (
                          <button
                            className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 font-medium px-3 py-1 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteProject(project.id, project.name);
                            }}
                          >
                            Delete
                          </button>
                        )}
                        <button
                          className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium px-3 py-1 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleScanClick(project);
                          }}
                        >
                          Scan
                        </button>
                      </div>
                    </div>

                    {/* Languages for GitHub repos only */}
                    {project.type === 'github' && project.languages && Object.keys(project.languages).length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {Object.keys(project.languages).slice(0, 5).map((lang) => (
                          <span
                            key={lang}
                            className="text-xs bg-gray-100 dark:bg-[#1f1f1f] text-gray-700 dark:text-gray-300 px-3 py-1 rounded-full"
                          >
                            {lang}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Security Analysis Link - Expandable on hover */}
                    <div className="grid grid-rows-[0fr] group-hover:grid-rows-[1fr] transition-all duration-300">
                      <div className="overflow-hidden">
                        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-[#2a2a2a]">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-500 dark:text-gray-400">Security Analysis:</span>
                            <Link
                              href={`/dashboard/security-analysis/${project.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium hover:underline"
                            >
                              Results
                            </Link>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pagination Controls */}
          {!loading && filteredProjects.length > PROJECTS_PER_PAGE && (
            <div className="p-4 border-t border-gray-200 dark:border-[#1f1f1f] flex items-center justify-between">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Showing {startIndex + 1}-{Math.min(startIndex + PROJECTS_PER_PAGE, filteredProjects.length)} of {filteredProjects.length} projects
              </p>
              <div className="flex items-center space-x-3">
                <button
                  onClick={handlePrevPage}
                  disabled={currentPage === 1}
                  className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ArrowLeftCircle className="w-8 h-8" />
                </button>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Page {currentPage}
                </span>
                <button
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition"
                >
                  <ArrowRightCircle className="w-8 h-8" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Scan Modal */}
      <ScanModal
        isOpen={scanModalOpen}
        onClose={() => {
          setScanModalOpen(false);
          setSelectedProject(null);
        }}
        project={selectedProject}
        onScanComplete={handleScanComplete}
      />
    </div>
  );
}
