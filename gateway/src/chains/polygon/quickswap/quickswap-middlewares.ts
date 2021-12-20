import { NextFunction, Request, Response } from 'express';
import {Quickswap} from "./quickswap";

export const verifyQuickswapIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const uniswap = Quickswap.getInstance();
  if (!uniswap.ready()) {
    await uniswap.init();
  }
  return next();
};
