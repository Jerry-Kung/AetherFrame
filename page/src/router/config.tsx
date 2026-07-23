import { lazy, Suspense } from "react";
import type { RouteObject } from "react-router-dom";
import NotFound from "../pages/NotFound";

const Home = lazy(() => import("../pages/home/page"));
const RepairPage = lazy(() => import("../pages/repair/page"));
const MaterialPage = lazy(() => import("../pages/material/page"));
const CreationPage = lazy(() => import("../pages/creation/page"));
const VideoPage = lazy(() => import("../pages/video/page"));

function PageFallback() {
  return (
    <div
      className="h-screen w-full flex items-center justify-center"
      style={{
        background: "linear-gradient(145deg, #fff5f7 0%, #fffaf5 45%, #fef2f8 80%, #fff8f0 100%)",
      }}
    >
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-rose-200 border-t-rose-400 animate-spin" />
        <span className="text-sm text-rose-400/70">加载中…</span>
      </div>
    </div>
  );
}

const routes: RouteObject[] = [
  {
    path: "/",
    element: (
      <Suspense fallback={<PageFallback />}>
        <Home />
      </Suspense>
    ),
  },
  {
    path: "/material",
    element: (
      <Suspense fallback={<PageFallback />}>
        <MaterialPage />
      </Suspense>
    ),
  },
  {
    path: "/repair",
    element: (
      <Suspense fallback={<PageFallback />}>
        <RepairPage />
      </Suspense>
    ),
  },
  {
    path: "/creation",
    element: (
      <Suspense fallback={<PageFallback />}>
        <CreationPage />
      </Suspense>
    ),
  },
  {
    path: "/video",
    element: (
      <Suspense fallback={<PageFallback />}>
        <VideoPage />
      </Suspense>
    ),
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

export default routes;
