import basler from "../../img/cameras/basler.png";
import realSenseRGBd from "../../img/cameras/realSenseRGBd.png";
import uvcRgb from "../../img/cameras/uvcRgb.png";
import styles from "./SupportedCameras.module.css";
import { CardItem } from "./CardItem/CardItem";

export const SupportedCameras = () => {
  return (
    <div>
      <h3 className={styles.title}>Supported cameras</h3>

      <div className={styles.items}>
        <CardItem name="UVC RGB" image={uvcRgb} />
        <CardItem name="RealSense RGBd" image={realSenseRGBd} />
        <CardItem name="Basler" image={basler} />
      </div>
    </div>
  );
};
