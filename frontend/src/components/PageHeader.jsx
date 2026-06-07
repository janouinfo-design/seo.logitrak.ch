export default function PageHeader({ overline, title, description, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div className="min-w-0">
        {overline && <div className="overline mb-2" data-testid="page-overline">{overline}</div>}
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight text-slate-950" data-testid="page-title">
          {title}
        </h1>
        {description && (
          <p className="mt-2 text-sm text-slate-600 max-w-2xl leading-relaxed">{description}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}
