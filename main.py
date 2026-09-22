def get_analysis(spot=None):
    df=yf.download("GC=F", period="2d", interval="1m", progress=False, auto_adjust=True)
    if len(df)<210: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    c=df["Close"]; h=df["High"]; l=df["Low"]

    df["MA20"]=c.rolling(20).mean()
    df["MA50"]=c.rolling(50).mean()
    df["MA100"]=c.rolling(100).mean()
    df["MA200"]=c.rolling(200).mean()
    df["RSI"]=rsi(c)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["ATR"]=tr.rolling(14).mean()

    last=df.iloc[-1]
    price=spot if spot else float(last["Close"])
    atr=float(last["ATR"])
    rsi_now=float(last["RSI"])

    # فيبو من اخر 100 شمعة - اوسع
    last100=df.tail(100)
    hi=float(last100["High"].max())
    lo=float(last100["Low"].min())
    diff=hi-lo
    fibs={"0.382":hi-diff*0.382, "0.5":hi-diff*0.5, "0.618":hi-diff*0.618}

    near_fib=None
    closest_dist=999
    for k,v in fibs.items():
        d=abs(price-v)
        if d < closest_dist:
            closest_dist=d
        if d < atr*1.5: # وسعت من 0.8 الى 1.5
            near_fib=f"{k} ({v:.2f})"
            break

    # لو ما لمس فيبو احفظ اقرب واحد للعرض فقط
    if not near_fib:
        # جيب اقرب فيبو
        nearest = min(fibs.items(), key=lambda x: abs(price - x[1]))
        near_fib_display = f"{nearest[0]} ({nearest[1]:.2f}) بعيد {closest_dist:.1f}$"
    else:
        near_fib_display = near_fib

    trend="عرضي"
    if last["MA20"]>last["MA50"]>last["MA100"]>last["MA200"]:
        trend="صاعد قوي"
    elif last["MA20"]<last["MA50"]<last["MA100"]<last["MA200"]:
        trend="هابط قوي"

    signal=None
    if near_fib: # الحين بيمسك اسرع
        if trend=="صاعد قوي" and rsi_now<=70 and rsi_now>=35:
            signal="شراء"
        elif trend=="هابط قوي" and rsi_now>=30 and rsi_now<=65:
            signal="بيع"

    return {"price":price,"trend":trend,"signal":signal,"rsi":rsi_now,"atr":atr,"fib":near_fib_display,"has_fib": near_fib is not None}
