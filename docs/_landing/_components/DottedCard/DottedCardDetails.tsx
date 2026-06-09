import { ReactNode } from "react";
import styles from "./DottedCard.module.css";

type DottedCardProps = {
  children: ReactNode;
};

export const DottedCard = ({ children }: DottedCardProps) => {
  return <div className={styles.container}>{children}</div>;
};
