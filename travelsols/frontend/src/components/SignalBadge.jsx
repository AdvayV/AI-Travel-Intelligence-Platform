export default function SignalBadge({ tier }) {
  return <span className={'badge tier-'+(tier||'watch').toLowerCase()}><span className="dot"/>{tier ? tier.toLowerCase() : 'watch'}</span>;
}
