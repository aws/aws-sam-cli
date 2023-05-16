import { lambdaHandler as localdepHandler } from "local-dependency";

export const lambdaHandler = async () => {
    result = await localdepHandler();
    return result
};
