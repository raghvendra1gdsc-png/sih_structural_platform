/**
 * frontend/lib/api.ts
 * Centralized API URL resolver with protocol normalization for Render / Vercel cloud deployments.
 */

export const getApiUrl = (): string => {
  let url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  url = url.trim();
  if (url && !url.startsWith("http://") && !url.startsWith("https://")) {
    return `https://${url}`;
  }
  return url;
};

export const API_BASE_URL = getApiUrl();
