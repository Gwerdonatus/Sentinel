import Link from "next/link";
import Image from "next/image";

export function SentinelMark({ className = "" }: { className?: string }) {
  return (
    <span className={`sentinel-mark ${className}`} aria-hidden="true">
      <Image
        src="/brand/sentinel-logo.png"
        alt=""
        width={1942}
        height={809}
        className="mark-source"
      />
    </span>
  );
}
export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Sentinel 2 home">
      <span className="brand-artwork">
        <Image
          src="/brand/sentinel-logo.png"
          alt="Sentinel"
          width={1942}
          height={809}
          className="brand-source"
          priority
        />
      </span>
      <span className="brand-version">2</span>
    </Link>
  );
}
export function PublicNav() {
  return (
    <header className="public-nav">
      <div className="public-nav-inner">
        <Brand />
        <nav aria-label="Main navigation">
          <Link href="/#platform">Platform</Link>
          <Link href="/developers">Developers</Link>
          <Link href="/status">Status</Link>
        </nav>
        <Link href="/dashboard" className="button button-dark">
          Open workspace <span aria-hidden="true">↗</span>
        </Link>
      </div>
    </header>
  );
}
