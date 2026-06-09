import styles from "./PolicyCard.module.css";

type PolicyCardProps = {
  title: string;
  listItems: string[];
};

export const PolicyCard = ({ title, listItems }: PolicyCardProps) => {
  return (
    <div className={styles.card}>
      <h3 className={styles.title}>{title}</h3>
      <ul className={styles.list}>
        {listItems.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
};
