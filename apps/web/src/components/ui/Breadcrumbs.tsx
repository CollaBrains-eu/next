import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="mb-3.5 flex flex-wrap items-center gap-1.5 text-[12.5px] text-ink-2" aria-label="Breadcrumb">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={`${item.label}-${index}`} className="flex items-center gap-1.5">
            {index > 0 && <span className="text-ink-3 text-[11px]">/</span>}
            {isLast || !item.to ? (
              <span className={isLast ? "font-semibold text-ink" : ""}>{item.label}</span>
            ) : (
              <Link
                to={item.to}
                className="rounded-md px-1 py-0.5 transition-colors duration-fast ease-out-token hover:bg-hover hover:text-accent"
              >
                {item.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
