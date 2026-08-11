import clsx from "clsx";
import { ReactNode } from "react";
import styles from "./DottedCard.module.css";

type DottedCardProps = {
  children: ReactNode;
  className?: string;
};

export const DottedCard = ({ children, className }: DottedCardProps) => {
  return <div className={clsx(styles.container, className)}>{children}</div>;
};
