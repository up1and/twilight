import { Route, Switch } from "wouter";
import Map from "./pages/map";
import Dashboard from "./pages/dashboard";

export default function App() {
  return (
    <Switch>
      <Route path="/" component={Map} />
      <Route path="/dashboard" component={Dashboard} />
    </Switch>
  );
}
