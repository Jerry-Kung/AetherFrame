const Header = () => {
  return (
    <div className="flex items-center gap-4 select-none">
      {/* Main title with cute font — temporarily hidden, pending redesign */}
      {/* <h1 
        className="text-3xl tracking-tight leading-none"
        style={{ fontFamily: "'ZCOOL KuaiLe', cursive" }}
      >
        <span
          className="text-transparent bg-clip-text"
          style={{
            backgroundImage:
              "linear-gradient(135deg, #f472b6 0%, #ec4899 40%, #db2777 100%)",
          }}
        >
          二次元美图开发引擎
        </span>
      </h1> */}

      {/* Subtle tagline in the middle — temporarily hidden with title */}
      {/* <span 
        className="text-sm tracking-wide"
        style={{ 
          color: "rgba(244, 114, 182, 0.45)",
          fontFamily: "'ZCOOL KuaiLe', cursive"
        }}
      >
        每一张图片都充满灵气
      </span> */}
    </div>
  );
};

export default Header;