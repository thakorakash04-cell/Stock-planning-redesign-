export function strToU8(value:string,latin1?:boolean):Uint8Array;
export function zipSync(files:Record<string,Uint8Array>,options?:{level?:number}):Uint8Array;
export function unzipSync(data:Uint8Array):Record<string,Uint8Array>;
export function gunzipSync(data:Uint8Array):Uint8Array;
