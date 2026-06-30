/**
 * 基于浏览器原生 Web Speech API 的 TTS 服务
 * 使用系统内置语音合成，无需第三方服务
 */

export type BrowserTtsOptions = {
  text: string;
  lang?: string;
  rate?: number;  // 0.1 - 10, 默认 1
  pitch?: number; // 0 - 2, 默认 1
  volume?: number; // 0 - 1, 默认 1
};

class BrowserTtsService {
  private isSupported: boolean;

  constructor() {
    this.isSupported = "speechSynthesis" in window;
  }

  /**
   * 检查浏览器是否支持 TTS
   */
  isAvailable(): boolean {
    return this.isSupported;
  }

  /**
   * 获取可用的语音列表
   */
  getVoices(): SpeechSynthesisVoice[] {
    if (!this.isSupported) return [];
    const voices = window.speechSynthesis.getVoices();
    // 优先返回中文语音
    const zhVoices = voices.filter(v => v.lang.includes('zh'));
    return zhVoices.length > 0 ? zhVoices : voices;
  }

  /**
   * 选择最佳中文语音
   */
  private selectBestVoice(): SpeechSynthesisVoice | null {
    const voices = this.getVoices();
    // 优先找中文语音
    const zhVoice = voices.find(v =>
      v.lang.includes('zh-CN') || v.lang.includes('zh-Hans')
    );
    return zhVoice || voices[0] || null;
  }

  /**
   * 合成语音（异步，等待播放完成）
   */
  async speak(options: BrowserTtsOptions): Promise<void> {
    if (!this.isSupported) {
      throw new Error("浏览器不支持 Web Speech API");
    }

    // 如果有正在播放的，先停止
    this.cancel();

    return new Promise((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(options.text);

      // 设置语音参数
      utterance.lang = options.lang || "zh-CN";
      utterance.rate = options.rate ?? 1;
      utterance.pitch = options.pitch ?? 1;
      utterance.volume = options.volume ?? 1;

      // 选择语音
      const voice = this.selectBestVoice();
      if (voice) {
        utterance.voice = voice;
      }

      utterance.onend = () => {
        resolve();
      };

      utterance.onerror = (event) => {
        // 用户取消不算错误
        if (event.error === "canceled" || event.error === "interrupted") {
          resolve();
        } else {
          reject(new Error(`TTS 错误: ${event.error}`));
        }
      };

      window.speechSynthesis.speak(utterance);
    });
  }

  /**
   * 取消当前播放
   */
  cancel(): void {
    if (this.isSupported) {
      window.speechSynthesis.cancel();
    }
  }

  /**
   * 暂停播放
   */
  pause(): void {
    if (this.isSupported && window.speechSynthesis.speaking) {
      window.speechSynthesis.pause();
    }
  }

  /**
   * 恢复播放
   */
  resume(): void {
    if (this.isSupported && window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
  }

  /**
   * 检查是否正在播放
   */
  isSpeaking(): boolean {
    return this.isSupported && window.speechSynthesis.speaking;
  }

  /**
   * 检查是否暂停
   */
  isPaused(): boolean {
    return this.isSupported && window.speechSynthesis.paused;
  }
}

// 单例
export const browserTtsService = new BrowserTtsService();
