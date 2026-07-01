import styles from "./CardItem.module.css";

type CardItemProps = {
  name: string;
  image: string;
};

export const CardItem = ({ name, image }: CardItemProps) => {
  return (
    <div className={styles.item}>
      <img src={image} alt={name} />
      <div>{name}</div>
    </div>
  );
};
