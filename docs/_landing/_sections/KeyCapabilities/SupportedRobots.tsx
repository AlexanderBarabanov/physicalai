import so101 from "../../img/robots/so101.png";
import trossenWidowX from "../../img/robots/so101.png";
import { CardItem } from "./CardItem/CardItem";
import styles from "./SupportedCameras.module.css";

export const SupportedRobots = () => {
  return (
    <div>
      <h3 className={styles.title}>Supported robots</h3>

      <div className={styles.items}>
        <CardItem name="SO-101" image={so101} />
        <CardItem name="Trossen WidowX (+bimanual)​" image={trossenWidowX} />
      </div>
    </div>
  );
};
