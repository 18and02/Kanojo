import * as PIXI from "pixi.js";
import {
  CubismConfig,
  Live2DModel,
  MotionPreloadStrategy,
  MotionPriority,
  config as live2dConfig
} from "pixi-live2d-display/cubism4";
import { useEffect, useRef, useState } from "react";

type AvatarMode = "idle" | "thinking" | "listening" | "speaking" | "interrupted";

export type Live2DStatus = "loading" | "ready" | "fallback";

type Live2DAvatarProps = {
  blinking: boolean;
  fallbackMouthLevel: number;
  mode: AvatarMode;
  mouthOpenY: number;
  onStatusChange?: (status: Live2DStatus) => void;
};

type CubismCoreModel = {
  setParameterValueById: (parameterId: string, value: number, weight?: number) => void;
  setPartOpacityById?: (partId: string, opacity: number) => void;
};

type DrawableBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type CubismHitArea = {
  index: number;
};

type CubismInternalModelWithBounds = Live2DModel["internalModel"] & {
  width: number;
  height: number;
  hitAreas?: Record<string, CubismHitArea>;
  getDrawableBounds?: (index: number, bounds?: Partial<DrawableBounds>) => DrawableBounds;
};

declare global {
  interface Window {
    PIXI?: typeof PIXI;
    Live2DCubismCore?: unknown;
  }
}

const DEFAULT_MODEL_URL = "./live2d/haru/haru_greeter_t03.model3.json";
const HARU_VISIBLE_PART_IDS = [
  "Part01Core",
  "Part01Hoho001",
  "Part01Brow001",
  "Part01Tear",
  "Part01EyeBall001",
  "Part01Eye001",
  "Part01Nose001",
  "Part01Mouth001",
  "Part01Face001",
  "Part01Ear001",
  "Part01Neck001",
  "Part01HairFront001",
  "Part01HairSide001",
  "Part01HairBack001",
  "Part01Body001"
];
const HARU_HIDDEN_PART_IDS = ["Part01Sketch"];

export function Live2DAvatar({
  blinking,
  fallbackMouthLevel,
  mode,
  mouthOpenY,
  onStatusChange
}: Live2DAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const modelRef = useRef<Live2DModel | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const modeRef = useRef(mode);
  const mouthOpenYRef = useRef(mouthOpenY);
  const [status, setStatus] = useState<Live2DStatus>("loading");

  const updateStatus = (nextStatus: Live2DStatus) => {
    setStatus(nextStatus);
    onStatusChange?.(nextStatus);
  };

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    mouthOpenYRef.current = mouthOpenY;
  }, [mouthOpenY]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let updateModelFrame: (() => void) | null = null;
    updateStatus(window.Live2DCubismCore ? "loading" : "fallback");
    if (!window.Live2DCubismCore) return;

    window.PIXI = PIXI;
    live2dConfig.sound = false;
    CubismConfig.setOpacityFromMotion = true;
    PIXI.utils.clearTextureCache();

    const app = new PIXI.Application({
      antialias: true,
      autoDensity: true,
      backgroundAlpha: 1,
      backgroundColor: 0xeef5f3,
      clearBeforeRender: true,
      resizeTo: container,
      resolution: Math.min(window.devicePixelRatio || 1, 2)
    });
    appRef.current = app;
    container.appendChild(app.view as HTMLCanvasElement);

    const applyLive2DParameters = () => {
      const model = modelRef.current;
      if (!model?.internalModel) return;
      const coreModel = model.internalModel.coreModel as CubismCoreModel;
      const pose = live2DPoseForMode(modeRef.current);
      coreModel.setParameterValueById("ParamMouthOpenY", mouthOpenYRef.current, 1);
      coreModel.setParameterValueById("ParamAngleX", pose.angleX, 0.22);
      coreModel.setParameterValueById("ParamAngleY", pose.angleY, 0.22);
      coreModel.setParameterValueById("ParamAngleZ", pose.angleZ, 0.18);
      coreModel.setParameterValueById("ParamBodyAngleX", pose.bodyAngleX, 0.18);
      applyHaruPartVisibility(coreModel);
    };

    const fitModel = () => {
      const model = modelRef.current;
      if (!model) return;
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      app.renderer.resize(width, height);
      const frame = getPreferredLive2DFrame(model);
      const scale = Math.min(width / frame.width, height / frame.height) * 0.9;
      model.scale.set(scale);
      model.x = width * 0.5 - (frame.x + frame.width * 0.5) * scale;
      model.y = height * 0.53 - (frame.y + frame.height * 0.5) * scale;
    };

    resizeObserverRef.current = new ResizeObserver(fitModel);
    resizeObserverRef.current.observe(container);

    Live2DModel.from(DEFAULT_MODEL_URL, {
      autoInteract: false,
      autoUpdate: false,
      motionPreload: MotionPreloadStrategy.IDLE
    })
      .then((model) => {
        if (disposed) {
          model.destroy({ children: true, texture: false, baseTexture: false });
          return;
        }
        modelRef.current = model;
        model.anchor.set(0, 0);
        model.internalModel.on("beforeModelUpdate", applyLive2DParameters);
        app.stage.addChild(model);
        updateModelFrame = () => {
          if (!disposed) {
            model.update(app.ticker.deltaMS || 16.67);
          }
        };
        app.ticker.add(updateModelFrame);
        applyLive2DParameters();
        model.update(16.67);
        fitModel();
        void model.motion("Idle", undefined, MotionPriority.IDLE);
        updateStatus("ready");
      })
      .catch((error) => {
        console.warn("Live2D avatar failed to load.", error);
        updateStatus("fallback");
      });

    return () => {
      disposed = true;
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      const model = modelRef.current;
      if (model) {
        model.internalModel?.off("beforeModelUpdate", applyLive2DParameters);
        if (updateModelFrame) {
          app.ticker.remove(updateModelFrame);
          updateModelFrame = null;
        }
        model.destroy({ children: true, texture: false, baseTexture: false });
        modelRef.current = null;
      }
      app.destroy(true, { children: true, texture: false, baseTexture: false });
      appRef.current = null;
    };
  }, []);

  return (
    <div className={`live2d-avatar ${status}`}>
      <div aria-hidden="true" className="live2d-canvas" ref={containerRef} />
      {status !== "ready" ? (
        <div
          aria-hidden="true"
          className={`avatar-figure ${blinking ? "blink" : ""}`}
          data-mouth={fallbackMouthLevel}
        >
          <div className="avatar-hair back" />
          <div className="avatar-neck" />
          <div className="avatar-face">
            <div className="avatar-fringe left" />
            <div className="avatar-fringe right" />
            <div className="avatar-eye left" />
            <div className="avatar-eye right" />
            <div className="avatar-cheek left" />
            <div className="avatar-cheek right" />
            <div className="avatar-mouth" />
          </div>
          <div className="avatar-shoulders" />
        </div>
      ) : null}
    </div>
  );
}

function live2DPoseForMode(mode: AvatarMode) {
  if (mode === "listening") {
    return { angleX: -8, angleY: 5, angleZ: -2, bodyAngleX: -4 };
  }
  if (mode === "thinking") {
    return { angleX: 7, angleY: 7, angleZ: 1, bodyAngleX: 3 };
  }
  if (mode === "speaking") {
    return { angleX: 2, angleY: 3, angleZ: 0, bodyAngleX: 1 };
  }
  if (mode === "interrupted") {
    return { angleX: 0, angleY: -7, angleZ: 3, bodyAngleX: 0 };
  }
  return { angleX: 0, angleY: 0, angleZ: 0, bodyAngleX: 0 };
}

function getPreferredLive2DFrame(model: Live2DModel): DrawableBounds {
  const internalModel = model.internalModel as CubismInternalModelWithBounds;
  const fullFrame = {
    x: 0,
    y: 0,
    width: Math.max(internalModel.width || 1, 1),
    height: Math.max(internalModel.height || 1, 1)
  };
  const headArea = internalModel.hitAreas?.Head;
  if (!headArea || typeof internalModel.getDrawableBounds !== "function") {
    return fullFrame;
  }

  const head = internalModel.getDrawableBounds(headArea.index, {});
  if (!isUsableBounds(head)) {
    return fullFrame;
  }

  const portraitHeight = Math.min(fullFrame.height, Math.max(head.height * 2.65, head.width * 2.9));
  const portraitWidth = Math.min(fullFrame.width, portraitHeight);
  const centerX = head.x + head.width * 0.5;
  const centerY = head.y + head.height * 0.92;

  return {
    x: clamp(centerX - portraitWidth * 0.5, 0, Math.max(fullFrame.width - portraitWidth, 0)),
    y: clamp(centerY - portraitHeight * 0.5, 0, Math.max(fullFrame.height - portraitHeight, 0)),
    width: portraitWidth,
    height: portraitHeight
  };
}

function isUsableBounds(bounds: DrawableBounds) {
  return (
    Number.isFinite(bounds.x) &&
    Number.isFinite(bounds.y) &&
    Number.isFinite(bounds.width) &&
    Number.isFinite(bounds.height) &&
    bounds.width > 0 &&
    bounds.height > 0
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function applyHaruPartVisibility(coreModel: CubismCoreModel) {
  for (const partId of HARU_VISIBLE_PART_IDS) {
    coreModel.setPartOpacityById?.(partId, 1);
  }
  for (const partId of HARU_HIDDEN_PART_IDS) {
    coreModel.setPartOpacityById?.(partId, 0);
  }
}
