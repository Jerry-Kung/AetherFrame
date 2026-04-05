import type { RouteObject } from "react-router-dom";
import NotFound from "../pages/NotFound";
import Home from "../pages/home/page";
import RepairPage from "../pages/repair/page";
import MaterialPage from "../pages/material/page";

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
    path: "*",
    element: <NotFound />,
  },
];

export default routes;
