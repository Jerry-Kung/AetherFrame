import type { RouteObject } from "react-router-dom";
import NotFound from "../pages/NotFound";
import Home from "../pages/home/page";
import RepairPage from "../pages/repair/page";

const routes: RouteObject[] = [
  {
    path: "/",
    element: <Home />,
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
