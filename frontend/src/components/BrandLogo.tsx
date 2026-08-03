type BrandLogoProps = {
  size?: number;
  color?: string;
  title?: string;
  className?: string;
  strokeWidth?: number;
};

/** 简笔黑白线条鸽子（原创线稿） */
export function BrandLogo({
  size = 28,
  color = "currentColor",
  title = "战鸽数据",
  className,
  strokeWidth = 1.7,
}: BrandLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role="img"
      aria-label={title}
      className={className}
      fill="none"
      style={{ display: "block", flexShrink: 0, color }}
    >
      <title>{title}</title>
      {/* head + beak */}
      <path
        d="M15.2 7.2c1.1-.9 2.5-1.1 3.6-.4.5.3.8.8.9 1.3"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M19.6 8.2h2.2l-1.1 1.1"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="17.35" cy="7.55" r="0.7" fill="currentColor" />
      {/* neck to breast */}
      <path
        d="M15.4 8.6c-.6 1.3-1.1 2.7-.8 4.1"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* wing */}
      <path
        d="M8.2 11.2c2.2-2.8 5.3-4.2 8.6-4.1"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9.2 13c1.8-1.8 4.1-2.8 6.6-2.9"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* body */}
      <path
        d="M6.8 12.8c-1.6.8-2.6 2.3-2.4 3.9.2 1.6 1.6 2.7 3.4 2.6 1.5-.1 2.9-.9 4-2"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* tail */}
      <path
        d="M6.2 16.4c-1.5.9-2.9 1.1-4.2.6M6.8 17.8c-1.3 1-2.6 1.3-4 .9"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* leg suggestion */}
      <path
        d="M11.2 16.8c-.2 1.5.1 2.9 1.1 4"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
