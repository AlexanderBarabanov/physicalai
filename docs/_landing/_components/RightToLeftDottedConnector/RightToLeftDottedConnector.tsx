import { useId } from "react";

export const RightToLeftDottedConnector = () => {
  const gradientId = `right-to-left-dotted-connector-${useId().replace(/:/g, "")}`;

  return (
    <div>
      <svg
        aria-hidden="true"
        focusable="false"
        role="presentation"
        width="253"
        height="64"
        viewBox="0 0 253 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0.500011 64L0.500003 39.9478C0.500001 35.5295 4.09468 31.9478 8.51296 31.9478C99.3361 31.9478 153.664 31.9478 244.487 31.9478C248.905 31.9478 252.5 28.3661 252.5 23.9478L252.5 5.43998e-06"
          stroke={`url(#${gradientId})`}
          strokeDasharray="4 4"
        />
        <defs>
          <linearGradient
            id={gradientId}
            x1="252.5"
            y1="31.7588"
            x2="0.94694"
            y2="31.7587"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#B57CFF" />
            <stop offset="1" stopColor="#70DBF3" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
};
