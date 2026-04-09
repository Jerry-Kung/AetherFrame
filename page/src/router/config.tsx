import type { RouteObject } from "react-router-dom";
import NotFound from "../pages/NotFound";
import Home from "../pages/home/page";
import RepairPage from "../pages/repair/page";
import MaterialPage from "../pages/material/page";
import CreationPage from "../pages/creation/page";

const routes: RouteObject[] = [
  {
    path: "/",
    element: <Home />,
  },
  {
    path: "/material",
    element: <MaterialPage />,
  },
  {
    path: "/repair",
    element: <RepairPage />,
  },
  {
    path: "/creation",
    element: <CreationPage />,
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

export default routes;
