// Reusable section heading for dense research screens.
type SectionHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
};

export const SectionHeader = ({ eyebrow, title, description }: SectionHeaderProps) => (
  <div className="max-w-3xl">
    {eyebrow ? (
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-secondary">{eyebrow}</p>
    ) : null}
    <h1 className="text-3xl font-bold tracking-normal text-white sm:text-4xl">{title}</h1>
    {description ? <p className="mt-3 text-base leading-7 text-slate-400">{description}</p> : null}
  </div>
);
