import { useId } from "react";

export const LeftToRightDottedConnector = () => {
  const gradientId = `left-to-right-dotted-connector-${useId().replace(/:/g, "")}`;

  return (
    <div>
      <svg
        aria-hidden="true"
        focusable="false"
        role="presentation"
        width="253"
        height="63"
        viewBox="0 0 253 63"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M252.5 63L252.5 39.4486C252.5 35.0303 248.905 31.4486 244.487 31.4486C153.664 31.4486 99.3361 31.4486 8.51297 31.4486C4.09468 31.4486 0.500012 27.8669 0.500032 23.4486L0.500139 -6.21104e-06"
          stroke={`url(#${gradientId})`}
          strokeDasharray="4 4"
        />
        <defs>
          <linearGradient
            id={gradientId}
            x1="0.500024"
            y1="31.2626"
            x2="252.053"
            y2="31.2625"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#70DBF3" />
            <stop offset="1" stopColor="#B57CFF" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
};
