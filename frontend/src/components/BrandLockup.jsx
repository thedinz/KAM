function BrandLockup({ compact = false }) {
  return (
    <span className={`kam-brand${compact ? ' kam-brand--compact' : ''}`}>
      <span className="kam-brand-mark" aria-hidden="true">
        <span className="kam-brand-mark-frame" />
        <span className="kam-brand-mark-letter">K</span>
      </span>
      <span className="kam-brand-copy">
        <span className="kam-brand-name">KAM</span>
        <span className="kam-brand-subtitle">Kometa Asset Manager</span>
      </span>
    </span>
  );
}

export default BrandLockup;
