import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROUTES } from "@/constants/routes";

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-5 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-cyan/10 text-cyan ring-1 ring-cyan/30">
        <Compass className="h-6 w-6" />
      </div>
      <div className="space-y-2">
        <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">404</p>
        <h1 className="text-display-lg font-semibold tracking-tight text-foreground">Page not found</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          The page you were looking for isn't here. It may have moved or never existed.
        </p>
      </div>
      <div className="flex gap-3">
        <Button asChild>
          <Link to={ROUTES.home}>Go home</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={ROUTES.dashboard}>Open dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
