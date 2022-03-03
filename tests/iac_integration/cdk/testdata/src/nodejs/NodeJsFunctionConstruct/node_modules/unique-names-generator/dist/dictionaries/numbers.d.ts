interface Config {
    min: number;
    max: number;
    length?: number;
}
export declare class NumberDictionary {
    static generate(config?: Partial<Config>): string[];
}
export {};
