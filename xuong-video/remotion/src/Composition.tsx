import {loadFont} from '@remotion/fonts';
import {Video} from '@remotion/media';
import {AbsoluteFill, Easing, Interactive, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

loadFont({family: 'DT-PhuDu', url: staticFile('DTPhudu-Black.otf')});

export const DosageBackground = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: 0, right: 0, top: 160, height: 420,
        background: 'linear-gradient(transparent, rgba(0,0,0,.60) 42%, rgba(0,0,0,.52) 63%, transparent)',
      }}/>
      <Interactive.Div name="Gạch nhấn liều lượng - không hình bình giả" style={{
        position: 'absolute', left: 148, top: 434, height: 5, backgroundColor: '#D2F29B',
        width: interpolate(frame, [0, 0.2 * fps], [0, 350], {
          extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}/>
    </AbsoluteFill>
  );
};

// Preview lettering stays native and editable in the actual CapCut draft.
export const DosagePreview = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      <Video name="Cảnh bình pha thật của nhà vườn" src={staticFile('TC01-mixing-real.mp4')} trimBefore={0.3 * fps} muted objectFit="cover" style={{width: '100%', height: '100%'}}/>
      <DosageBackground/>
      <Interactive.Div name="Nhãn chai - chữ mẫu" style={{position: 'absolute', left: 148, top: 284, color: '#FFFFFF', fontSize: 32, fontFamily: "'Segoe UI', sans-serif", fontWeight: 600, letterSpacing: 1.2, textShadow: '0 2px 12px #0008'}}>
        1 CHAI 100 ML
      </Interactive.Div>
      <Interactive.Div name="Liều pha - chữ mẫu" style={{
        position: 'absolute', left: 144, top: 325, color: '#FFFFFF', fontSize: 84,
        fontFamily: "'Segoe UI', sans-serif", fontWeight: 700, letterSpacing: -1.8, textShadow: '0 3px 16px #0008',
        opacity: interpolate(frame, [0, 0.12 * fps], [0, 1], {extrapolateRight: 'clamp'}),
        translate: interpolate(frame, [0, 0.16 * fps], ['0px 10px', '0px 0px'], {
          extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}>
        5 BÌNH × 20 LÍT
      </Interactive.Div>
      <Interactive.Div name="Phụ đề mẫu DT-PhuDu" style={{position: 'absolute', left: 80, right: 80, top: 1500, textAlign: 'center', fontFamily: 'DT-PhuDu', fontSize: 64, color: '#FFD65A', textShadow: '-3px -3px #073C2F, 3px 3px #073C2F', opacity: frame >= 4 ? 1 : 0}}>
        5 bình 20 lít
      </Interactive.Div>
    </AbsoluteFill>
  );
};
