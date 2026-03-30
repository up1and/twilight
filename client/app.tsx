import { lazy, Suspense } from "react";
import { Route, Switch } from "wouter";
import { LoaderCircle } from "lucide-react";
import Map from "./pages/map";

const Dashboard = lazy(() => import("./pages/dashboard"));

function Loading() {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh"
      }}
    >
      <LoaderCircle className="animate-spin" size={48} />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Switch>
        <Route path="/" component={Map} />
        <Route path="/dashboard" component={Dashboard} />
      </Switch>
    </Suspense>
  );
}
