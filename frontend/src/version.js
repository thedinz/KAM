// Keep this aligned with the KAM release tag before publishing a release.
export const KAM_VERSION_NUMBER = '7.1.0';

function normalizeBranchName(value) {
  const text = String(value || '').trim();
  if (!text) return 'dev';
  return text
    .replace(/^refs\/heads\//, '')
    .replace(/^origin\//, '')
    .replace(/[^0-9A-Za-z._-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'dev';
}

const injectedBranch =
  typeof __KAM_BRANCH__ === 'string' ? __KAM_BRANCH__ : '';
const envBranch =
  typeof import.meta !== 'undefined'
    ? import.meta.env?.VITE_KAM_BRANCH || import.meta.env?.VITE_GIT_BRANCH || ''
    : '';

export const KAM_VERSION_BRANCH = normalizeBranchName(envBranch || injectedBranch);
export const KAM_VERSION = `${KAM_VERSION_NUMBER}:${KAM_VERSION_BRANCH}`;
