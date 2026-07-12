import { lazy, Suspense, useEffect, useState } from "react";
import { Route, Switch, useLocation } from "wouter";
import { LoaderCircle } from "lucide-react";
import Map from "./views/map";
import Login from "./views/login";
import { verifyToken } from "./utils/api-client";
import { storage } from "./utils/storage";

const Dashboard = lazy(() => import("./views/dashboard"));

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

function ProtectedRoute({ component: Component }: { component: React.ComponentType }) {
  const [, setLocation] = useLocation();
  const [isValidating, setIsValidating] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = storage.get("auth-token");
      if (!token) {
        setIsAuthorized(false);
        setIsValidating(false);
        return;
      }

      const valid = await verifyToken(token);
      if (valid) {
        setIsAuthorized(true);
      } else {
        storage.set("auth-token", null);
        setLocation("/login");
      }
      setIsValidating(false);
    };

    checkAuth();
  }, [setLocation]);

  if (isValidating) {
    return <Loading />;
  }

  if (!isAuthorized) {
    setLocation("/login");
    return null;
  }

  return <Component />;
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Switch>
        <Route path="/login" component={Login} />
        <Route path="/dashboard">
          {() => <ProtectedRoute component={Dashboard} />}
        </Route>
        <Route path="/" component={Map} />
      </Switch>
    </Suspense>
  );
}
