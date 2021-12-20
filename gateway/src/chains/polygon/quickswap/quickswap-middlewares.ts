import { Quickswap } from './quickswap';
import { NextFunction, Request, Response } from 'express';

export const verifyQuickswapIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const quickswap = Quickswap.getInstance();
  if (!quickswap.ready()) {
    await quickswap.init();
  }
  return next();
};
