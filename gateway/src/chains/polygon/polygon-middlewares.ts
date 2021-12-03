import { NextFunction, Request, Response } from 'express';
import {Polygon} from "./polygon";

export const verifyEthereumIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const polygon = Polygon.getInstance();
  if (!polygon.ready()) {
    await polygon.init();
  }
  return next();
};
